import io
import json
import logging
import re
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.validators import validate_email
from django.db.models import F
from django.http import FileResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.utils.text import get_valid_filename

from PIL import Image

from .models import PageView, ContactLead, JobApplication, PostBlog, Evento, Especialidade, NewsletterInscricao, Ebook, PostVisualizacao, Carrossel, SobreNosFoto, Cliente
from .whatsapp import send_lead_to_whatsapp
from . import security

logger = logging.getLogger(__name__)

# Limites de segurança para o endpoint de contato
MAX_BODY_BYTES = 10 * 1024  # 10 KB
CONTACT_RATE_LIMIT = 5       # máx. de requisições por janela
CONTACT_RATE_WINDOW = 60     # janela em segundos
HONEYPOT_FIELD = 'website'   # campo oculto; se preenchido, é bot

CELULAR_RE = re.compile(r'^\d{10,13}$')

# Limites e validação do currículo (Trabalhe Conosco)
MAX_CURRICULO_BYTES = 5 * 1024 * 1024        # 5 MB
CURRICULO_FORM_OVERHEAD = 512 * 1024         # folga para os campos do formulário multipart
ALLOWED_CURRICULO_EXTS = {'.pdf', '.doc', '.docx'}
SIGNATURE_SIZE = 8

# Magic bytes para detectar o tipo real do arquivo (não confia no MIME enviado pelo cliente)
CURRICULO_MAGIC = {
    '.pdf': (b'%PDF',),                                      # PDF
    '.doc': (b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1',),         # OLE2 / Compound Document
    '.docx': (b'PK\x03\x04',),                               # ZIP (docx é um contêiner zip)
}


def _detecta_curriculo_type(content: bytes):
    """Retorna a extensão correspondente aos magic bytes, ou None se não reconhecer."""
    for ext, signatures in CURRICULO_MAGIC.items():
        for sig in signatures:
            if content[: len(sig)] == sig:
                return ext
    return None


def _gera_preview_curriculo(candidatura):
    """Gera a imagem da 1ª página do currículo (apenas PDFs) e salva no campo 'preview'.

    DOC/DOCX não têm renderização de imagem portável: ficam sem preview e o admin
    exibe um ícone do tipo. Falhas na geração nunca derrubam a candidatura.
    """
    if not candidatura.curriculo:
        return
    try:
        if Path(candidatura.curriculo.name).suffix.lower() != '.pdf':
            return
        import pypdfium2 as pdfium

        candidatura.curriculo.open('rb')
        try:
            pdf = pdfium.PdfDocument(candidatura.curriculo.read())
        finally:
            candidatura.curriculo.close()

        if len(pdf) == 0:
            return
        imagem = pdf[0].render(scale=1.5).to_pil()

        # Garante fundo branco (PDFs podem ter transparência)
        if imagem.mode in ('RGBA', 'LA'):
            alpha = imagem.split()[-1]
            fundo = Image.new('RGB', imagem.size, (255, 255, 255))
            fundo.paste(imagem.convert('RGBA'), mask=alpha)
            imagem = fundo
        else:
            imagem = imagem.convert('RGB')

        buf = io.BytesIO()
        imagem.save(buf, format='PNG')
        nome_preview = Path(candidatura.curriculo.name).stem + '.png'
        candidatura.preview.save(nome_preview, ContentFile(buf.getvalue()), save=True)
    except Exception:
        pass


def _valida_celular(value: str) -> bool:
    """Aceita celular BR com 10 a 13 dígitos (com ou sem +55), ignorando formatação."""
    return bool(CELULAR_RE.match(re.sub(r'\D', '', value)))


def _valida_cnpj(value: str) -> bool:
    """Valida formato e dígitos verificadores de um CNPJ."""
    cnpj = re.sub(r'\D', '', value)
    if len(cnpj) != 14 or cnpj == cnpj[0] * 14:
        return False

    def digito(digs, pesos):
        resto = sum(int(d) * p for d, p in zip(digs, pesos)) % 11
        return 0 if resto < 2 else 11 - resto

    if digito(cnpj[:12], [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]) != int(cnpj[12]):
        return False
    return digito(cnpj[:13], [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]) == int(cnpj[13])


def _valida_cpf(value: str) -> bool:
    """Valida formato e dígitos verificadores de um CPF."""
    cpf = re.sub(r'\D', '', value)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    for tam in (9, 10):
        resto = sum(int(d) * (tam + 1 - i) for i, d in enumerate(cpf[:tam])) % 11
        digito = 0 if resto < 2 else 11 - resto
        if int(cpf[tam]) != digito:
            return False
    return True


def _contact_rate_limited(ip: str) -> bool:
    """True se o IP estourou o limite de requisições na janela de tempo."""
    if not ip:
        return False
    start_key = f'contact_rate_start:{ip}'
    hits_key = f'contact_rate_hits:{ip}'
    window_start = cache.get(start_key, 0)
    if time.time() - window_start > CONTACT_RATE_WINDOW:
        cache.set(start_key, time.time(), CONTACT_RATE_WINDOW)
        cache.set(hits_key, 0, CONTACT_RATE_WINDOW)
    hits = cache.get(hits_key, 0)
    if hits >= CONTACT_RATE_LIMIT:
        return True
    cache.set(hits_key, hits + 1, CONTACT_RATE_WINDOW)
    return False


def _get_client_ip(request):
    """Retorna o IP do visitante, respeitando proxies (X-Forwarded-For)."""
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '').strip()


MESES_PT = [
    'janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho',
    'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro',
]

MESES_ABREV = [
    'JAN', 'FEV', 'MAR', 'ABR', 'MAI', 'JUN',
    'JUL', 'AGO', 'SET', 'OUT', 'NOV', 'DEZ',
]


def _formata_data(dt):
    """Formata uma data no padrão '15 de janeiro de 2024'."""
    return f"{dt.day} de {MESES_PT[dt.month - 1]} de {dt.year}"


def _formata_data_evento(dt):
    """Formata a data de um evento no padrão '15 OUT' (dia + mês abreviado)."""
    return f"{dt.day:02d} {MESES_ABREV[dt.month - 1]}"


def list_posts(request):
    """Lista os posts publicados do blog, do mais recente ao mais antigo."""
    posts = PostBlog.objects.filter(status='publicado').order_by('-data_publicacao')

    data = {
        'posts': [
            {
                'titulo': post.titulo,
                'resumo': post.resumo,
                'data_publicacao': _formata_data(post.data_publicacao) if post.data_publicacao else '',
                'data_iso': post.data_publicacao.date().isoformat() if post.data_publicacao else '',
                'imagem': request.build_absolute_uri(post.imagem_destaque.url) if post.imagem_destaque else '',
                'slug': post.slug,
            }
            for post in posts
        ]
    }

    return JsonResponse(data)


def detalhe_post(request, slug):
    """Retorna os dados completos de um post publicado pelo seu slug.

    O contador de visualizações conta 1 por IP por artigo: na primeira
    abertura daquele IP o contador sobe; nas seguintes, permanece igual.
    """
    try:
        post = PostBlog.objects.get(slug=slug, status='publicado')
    except PostBlog.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Post não encontrado'}, status=404)

    ip = _get_client_ip(request)
    if ip:
        vis, created = PostVisualizacao.objects.get_or_create(post=post, ip_address=ip)
        if created:
            PostBlog.objects.filter(pk=post.pk).update(visualizacoes=F('visualizacoes') + 1)
            post.refresh_from_db()
    else:
        PostBlog.objects.filter(pk=post.pk).update(visualizacoes=F('visualizacoes') + 1)
        post.refresh_from_db()

    data = {
        'post': {
            'titulo': post.titulo,
            'resumo': post.resumo,
            'conteudo': post.conteudo,
            'data_publicacao': _formata_data(post.data_publicacao) if post.data_publicacao else '',
            'imagem': request.build_absolute_uri(post.imagem_destaque.url) if post.imagem_destaque else '',
            'slug': post.slug,
            'autor': post.autor.get_full_name() or post.autor.username,
            'visualizacoes': post.visualizacoes,
        }
    }

    return JsonResponse(data)


def list_eventos(request):
    """Lista os eventos ativos e futuros, do mais próximo ao mais distante."""
    eventos = Evento.objects.filter(
        ativo=True,
        data_inicio__gte=timezone.now(),
    ).order_by('data_inicio')

    data = {
        'eventos': [
            {
                'titulo': evento.titulo,
                'descricao': evento.descricao,
                'local': evento.local,
                'data': _formata_data_evento(evento.data_inicio),
                'data_completa': _formata_data(evento.data_inicio),
                'imagem': request.build_absolute_uri(evento.imagem.url) if evento.imagem else '',
                'link_inscricao': evento.link_inscricao or '',
            }
            for evento in eventos
        ]
    }

    return JsonResponse(data)


@csrf_exempt
@require_POST
def record_pageview(request):
    """Registra uma visita ao site"""
    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        data = {}

    path = data.get('path', request.META.get('HTTP_REFERER', '/'))
    ip_address = _get_client_ip(request)
    user_agent = request.META.get('HTTP_USER_AGENT', '')

    PageView.objects.create(
        path=path,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    return JsonResponse({'status': 'ok'})


@csrf_exempt
@require_POST
def submit_contact(request):
    """Registra um lead do formulário de contato e notifica o WhatsApp do Gilton.

    Proteções: limite de tamanho do body, rate limit por IP, honeypot anti-bot
    e validação estrita dos campos.
    """
    if request.headers.get('Content-Length'):
        try:
            if int(request.headers['Content-Length']) > MAX_BODY_BYTES:
                return JsonResponse({'status': 'error', 'message': 'Requisição muito grande.'}, status=413)
        except ValueError:
            pass

    ip = _get_client_ip(request)
    if _contact_rate_limited(ip):
        security.registrar_rate_limit(request, ip)
        return JsonResponse(
            {'status': 'error', 'message': 'Muitas requisições. Tente novamente mais tarde.'},
            status=429,
        )

    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'JSON inválido.'}, status=400)

    if not isinstance(data, dict):
        return JsonResponse({'status': 'error', 'message': 'JSON inválido.'}, status=400)

    # Honeypot: se preenchido, é bot -> responde sucesso mas descarta o lead
    if data.get(HONEYPOT_FIELD):
        security.registrar_honeypot(request, ip)
        return JsonResponse({'status': 'ok', 'message': 'Dados enviados com sucesso!'})

    nome = data.get('nome', '').strip()
    celular = data.get('celular', '').strip()
    email = data.get('email', '').strip()
    cpf = data.get('cpf', '').strip()
    cnpj = data.get('cnpj', '').strip()
    mensagem = data.get('mensagem', '').strip()

    # Origem e interesse informados pelos formulários (valores validados contra o modelo)
    origem = data.get('origem', '').strip()
    interesse = data.get('interesse', '').strip()
    origens_validas = dict(ContactLead.ORIGEM_CHOICES)
    interesses_validos = dict(ContactLead.INTERESSE_CHOICES)
    if origem not in origens_validas:
        origem = 'site'
    if interesse not in interesses_validos:
        interesse = 'geral'

    errors = []
    if not 2 <= len(nome) <= 200:
        errors.append('Informe um nome válido (entre 2 e 200 caracteres).')
    if not _valida_celular(celular):
        errors.append('Informe um celular válido.')
    if not email:
        errors.append('Informe o e-mail.')
    else:
        try:
            validate_email(email)
        except ValidationError:
            errors.append('Informe um e-mail válido.')
    if cpf and not _valida_cpf(cpf):
        errors.append('CPF inválido.')
    if cnpj and not _valida_cnpj(cnpj):
        errors.append('CNPJ inválido.')
    if len(mensagem) > 2000:
        errors.append('Mensagem muito longa (máx. 2000 caracteres).')

    if errors:
        return JsonResponse({'status': 'error', 'message': ' '.join(errors)}, status=400)

    ContactLead.objects.create(
        nome=nome,
        celular=celular,
        email=email,
        cpf=cpf,
        cnpj=cnpj,
        mensagem=mensagem,
        origem=origem,
        interesse=interesse,
    )

    send_lead_to_whatsapp({
        'nome': nome,
        'celular': celular,
        'email': email,
        'cnpj': cnpj,
        'mensagem': mensagem,
    })

    return JsonResponse({'status': 'ok', 'message': 'Dados enviados com sucesso!'})


@csrf_exempt
@require_POST
def track_whatsapp_click(request):
    """Registra um clique direto em um link de WhatsApp (wa.me) do site.

    Diferente do formulário de contato, aqui não há nome/e-mail do visitante:
    apenas registramos que houve o contato, de onde veio e o interesse apontado.
    """
    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'JSON inválido.'}, status=400)

    if not isinstance(data, dict):
        return JsonResponse({'status': 'error', 'message': 'JSON inválido.'}, status=400)

    ip = _get_client_ip(request)
    if _contact_rate_limited(ip):
        security.registrar_rate_limit(request, ip)
        return JsonResponse(
            {'status': 'error', 'message': 'Muitas requisições. Tente novamente mais tarde.'},
            status=429,
        )

    origem_pagina = str(data.get('origem_pagina', '')).strip()[:50] or 'site'
    interesse = str(data.get('interesse', '')).strip()
    if interesse not in dict(ContactLead.INTERESSE_CHOICES):
        interesse = 'geral'

    ContactLead.objects.create(
        nome='',
        celular='',
        email='',
        origem='whatsapp_direto',
        interesse=interesse,
        mensagem=f'Clique em link de WhatsApp (página: {origem_pagina})',
    )

    return JsonResponse({'status': 'ok'})


@csrf_exempt
@require_POST
def login_cliente(request):
    """Cadastra/loga um cliente (auto-cadastro) e registra o acesso ao serviço.

    Proteções: reCAPTCHA v2, honeypot, rate limit por IP e validação estrita
    dos campos. O cliente é identificado por e-mail ou CPF: se já existe,
    atualiza os dados; senão, cria a conta. Devolve um token de sessão.
    """
    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'JSON inválido.'}, status=400)

    if not isinstance(data, dict):
        return JsonResponse({'status': 'error', 'message': 'JSON inválido.'}, status=400)

    ip = _get_client_ip(request)
    if _contact_rate_limited(ip):
        security.registrar_rate_limit(request, ip)
        return JsonResponse(
            {'status': 'error', 'message': 'Muitas requisições. Tente novamente mais tarde.'},
            status=429,
        )

    # Honeypot: se preenchido, é bot -> responde sucesso mas descarta
    if data.get(HONEYPOT_FIELD):
        security.registrar_honeypot(request, ip)
        return JsonResponse({'status': 'ok', 'message': 'Dados enviados com sucesso!'})

    if not _verifica_recaptcha(data.get('g-recaptcha-response', '')):
        security.registrar_falha_recaptcha(request, ip)
        return JsonResponse({'status': 'error', 'message': 'Confirme que você não é um robô.'}, status=400)

    nome = data.get('nome', '').strip()
    email = data.get('email', '').strip()
    celular = data.get('celular', '').strip()
    cpf = data.get('cpf', '').strip()
    cnpj = data.get('cnpj', '').strip()
    interesse = data.get('interesse', '').strip()
    if interesse not in dict(ContactLead.INTERESSE_CHOICES):
        interesse = 'geral'

    errors = []
    if not 2 <= len(nome) <= 200:
        errors.append('Informe um nome válido (entre 2 e 200 caracteres).')
    if not email:
        errors.append('Informe o e-mail.')
    else:
        try:
            validate_email(email)
        except ValidationError:
            errors.append('Informe um e-mail válido.')
    if not _valida_celular(celular):
        errors.append('Informe um celular válido.')
    if cpf and not _valida_cpf(cpf):
        errors.append('CPF inválido.')
    if cnpj and not _valida_cnpj(cnpj):
        errors.append('CNPJ inválido.')
    if errors:
        return JsonResponse({'status': 'error', 'message': ' '.join(errors)}, status=400)

    cpf_normalizado = re.sub(r'\D', '', cpf) or None

    cliente = Cliente.objects.filter(email__iexact=email).first()
    if not cliente and cpf_normalizado:
        cliente = Cliente.objects.filter(cpf=cpf_normalizado).first()

    if cliente:
        cliente.nome = nome
        cliente.celular = celular
        if cnpj:
            cliente.cnpj = cnpj
    else:
        cliente = Cliente(
            nome=nome,
            email=email.lower(),
            celular=celular,
            cpf=cpf_normalizado,
            cnpj=cnpj,
        )

    if not cliente.auth_token:
        cliente.auth_token = secrets.token_urlsafe(32)
    cliente.ultimo_acesso = timezone.now()
    cliente.save()

    ContactLead.objects.create(
        nome=nome,
        celular=celular,
        email=email,
        cpf=cpf,
        cnpj=cnpj,
        mensagem='Acesso a serviço via login (Soluções).',
        origem='solucoes',
        interesse=interesse,
    )

    send_lead_to_whatsapp({
        'nome': nome,
        'celular': celular,
        'email': email,
        'cnpj': cnpj,
    })

    return JsonResponse({
        'status': 'ok',
        'message': 'Login realizado com sucesso!',
        'token': cliente.auth_token,
        'cliente': {
            'nome': cliente.nome,
            'email': cliente.email,
            'celular': cliente.celular,
            'cpf': cliente.cpf or '',
            'cnpj': cliente.cnpj,
        },
    })


@csrf_exempt
@require_POST
def registrar_acesso_cliente(request):
    """Registra um acesso a serviço de um cliente já logado (token válido).

    Mantém o relatório Comercial atualizado mesmo quando o cliente já está
    logado e apenas clica em um serviço. Token inválido -> 401.
    """
    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'JSON inválido.'}, status=400)

    if not isinstance(data, dict):
        return JsonResponse({'status': 'error', 'message': 'JSON inválido.'}, status=400)

    ip = _get_client_ip(request)
    if _contact_rate_limited(ip):
        security.registrar_rate_limit(request, ip)
        return JsonResponse(
            {'status': 'error', 'message': 'Muitas requisições. Tente novamente mais tarde.'},
            status=429,
        )

    token = str(data.get('token', '')).strip()
    if not token:
        return JsonResponse({'status': 'error', 'message': 'Não autenticado.'}, status=401)

    cliente = Cliente.objects.filter(auth_token=token).first()
    if not cliente:
        return JsonResponse({'status': 'error', 'message': 'Sessão expirada. Faça login novamente.'}, status=401)

    interesse = str(data.get('interesse', '')).strip()
    if interesse not in dict(ContactLead.INTERESSE_CHOICES):
        interesse = 'geral'

    cliente.ultimo_acesso = timezone.now()
    cliente.save(update_fields=['ultimo_acesso'])

    ContactLead.objects.create(
        nome=cliente.nome,
        celular=cliente.celular,
        email=cliente.email,
        cpf=cliente.cpf or '',
        cnpj=cliente.cnpj,
        mensagem='Acesso a serviço de Soluções (cliente já logado).',
        origem='solucoes',
        interesse=interesse,
    )

    return JsonResponse({'status': 'ok'})


def _verifica_recaptcha(response_token: str) -> bool:
    """Valida o token do reCAPTCHA v2 junto ao Google.

    Sem RECAPTCHA_SECRET_KEY configurado (ex.: desenvolvimento local sem chaves),
    aceita e registra um aviso — mesmo padrão das credenciais do WhatsApp.
    Token ausente ou inválido é rejeitado. Falha de rede com o Google é tratada
    como aceite para não bloquear candidatos reais.
    """
    secret = getattr(settings, 'RECAPTCHA_SECRET_KEY', '').strip()
    if not secret:
        logger.warning('[reCAPTCHA] RECAPTCHA_SECRET_KEY nao configurada; verificacao ignorada.')
        return True

    if not response_token:
        return False

    data = urllib.parse.urlencode({
        'secret': secret,
        'response': response_token,
    }).encode('utf-8')
    req = urllib.request.Request(
        'https://www.google.com/recaptcha/api/siteverify',
        data=data,
        method='POST',
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode('utf-8'))
            return bool(body.get('success'))
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError, OSError) as exc:
        logger.error('[reCAPTCHA] Falha ao verificar token: %s', exc)
        return True


@csrf_exempt
@require_POST
def submit_job_application(request):
    """Registra uma candidatura (Trabalhe Conosco) com currículo em PDF, DOC ou DOCX.

    Proteções: reCAPTCHA v2, honeypot, limite de tamanho (antecipado via
    Content-Length e por arquivo), tipo real validado por magic bytes, extensão
    restrita, nome sanitizado, e-mail validado e rate limit por IP.
    """
    # Rejeita cedo requisições grandes (evita flood de uploads)
    content_length = request.META.get('CONTENT_LENGTH')
    if content_length:
        try:
            if int(content_length) > MAX_CURRICULO_BYTES + CURRICULO_FORM_OVERHEAD:
                return JsonResponse(
                    {'status': 'error', 'message': 'Arquivo muito grande. O limite é 5 MB.'},
                    status=413,
                )
        except ValueError:
            pass

    ip = _get_client_ip(request)
    if _contact_rate_limited(ip):
        security.registrar_rate_limit(request, ip)
        return JsonResponse(
            {'status': 'error', 'message': 'Muitas requisições. Tente novamente mais tarde.'},
            status=429,
        )

    nome = request.POST.get('nome', '').strip()
    email = request.POST.get('email', '').strip()
    telefone = request.POST.get('telefone', '').strip()
    mensagem = request.POST.get('mensagem', '').strip()
    curriculo_file = request.FILES.get('curriculo')
    recaptcha_response = request.POST.get('g-recaptcha-response', '')
    website_honeypot = request.POST.get('website', '').strip()

    # Honeypot: campo oculto que nenhum humano preenche. Se veio preenchido,
    # descarta silenciosamente como se tivesse dado certo (não revela o bloqueio).
    if website_honeypot:
        security.registrar_honeypot(request, ip)
        return JsonResponse({'status': 'ok', 'message': 'Candidatura registrada com sucesso!'})

    errors = []
    if not _verifica_recaptcha(recaptcha_response):
        security.registrar_falha_recaptcha(request, ip)
        errors.append('Confirme que você não é um robô.')
    if not 2 <= len(nome) <= 200:
        errors.append('Informe um nome válido (entre 2 e 200 caracteres).')
    if not email:
        errors.append('Informe o e-mail.')
    else:
        try:
            validate_email(email)
        except ValidationError:
            errors.append('Informe um e-mail válido.')

    if not curriculo_file:
        errors.append('Anexe seu currículo.')
    else:
        if curriculo_file.size > MAX_CURRICULO_BYTES:
            errors.append('Arquivo muito grande. O limite é 5 MB.')
        else:
            ext = Path(curriculo_file.name).suffix.lower()
            if ext not in ALLOWED_CURRICULO_EXTS:
                errors.append('Formato não permitido. Envie PDF, DOC ou DOCX.')
            else:
                curriculo_file.seek(0)
                assinatura = curriculo_file.read(SIGNATURE_SIZE)
                if _detecta_curriculo_type(assinatura) != ext:
                    errors.append('O conteúdo do arquivo não corresponde ao formato informado.')
                curriculo_file.seek(0)

    if errors:
        return JsonResponse({'status': 'error', 'message': ' '.join(errors)}, status=400)

    curriculo_file.name = get_valid_filename(curriculo_file.name)

    candidatura = JobApplication.objects.create(
        nome=nome,
        email=email,
        telefone=telefone,
        mensagem=mensagem,
        curriculo=curriculo_file,
    )
    _gera_preview_curriculo(candidatura)

    return JsonResponse({'status': 'ok', 'message': 'Candidatura registrada com sucesso!'})


@csrf_exempt
@require_POST
def subscribe_newsletter(request):
    """Cadastra o e-mail de um cliente na newsletter"""
    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'JSON inválido'}, status=400)

    email = data.get('email', '').strip()
    nome = data.get('nome', '').strip()[:200]
    celular = data.get('celular', '').strip()[:30]
    origem = data.get('origem', 'footer').strip()

    if not email:
        return JsonResponse({'status': 'error', 'message': 'Informe seu e-mail'}, status=400)

    from django.core.validators import validate_email
    from django.core.exceptions import ValidationError
    try:
        validate_email(email)
    except ValidationError:
        return JsonResponse({'status': 'error', 'message': 'E-mail inválido'}, status=400)

    if origem not in dict(NewsletterInscricao.ORIGEM_CHOICES):
        origem = 'footer'

    inscricao, created = NewsletterInscricao.objects.get_or_create(
        email=email.lower(),
        defaults={'origem': origem},
    )

    if nome:
        inscricao.nome = nome
    if celular:
        inscricao.celular = celular
    inscricao.save()

    if created:
        return JsonResponse({'status': 'ok', 'message': 'E-mail cadastrado com sucesso!'})
    return JsonResponse({'status': 'ok', 'message': 'E-mail já cadastrado!'})


def list_carrossel(request):
    """Lista as imagens ativas do carrossel do hero, ordenadas por 'ordem'."""
    slides = Carrossel.objects.filter(ativo=True).order_by('ordem', 'data_criacao')

    def _botao(slide, prefix):
        return {
            'texto': getattr(slide, f'{prefix}_texto'),
            'tipo': getattr(slide, f'{prefix}_tipo'),
            'link': getattr(slide, f'{prefix}_link'),
        }

    data = {
        'slides': [
            {
                'id': slide.pk,
                'titulo': slide.titulo,
                'subtitulo': slide.subtitulo,
                'imagem': request.build_absolute_uri(slide.imagem.url) if slide.imagem else '',
                'foto': request.build_absolute_uri(slide.foto.url) if slide.foto else '',
                'ordem': slide.ordem,
                'botao1': _botao(slide, 'botao1'),
                'botao2': _botao(slide, 'botao2'),
            }
            for slide in slides
        ]
    }

    return JsonResponse(data)


def list_sobre_nos_fotos(request):
    """Lista as fotos ativas do carrossel 3D da seção Sobre Nós, ordenadas por 'ordem'."""
    fotos = SobreNosFoto.objects.filter(ativo=True).order_by('ordem', 'data_criacao')

    data = {
        'fotos': [
            {
                'id': foto.pk,
                'titulo': foto.titulo,
                'imagem': request.build_absolute_uri(foto.imagem.url) if foto.imagem else '',
                'ordem': foto.ordem,
            }
            for foto in fotos
        ]
    }

    return JsonResponse(data)


def list_especialidades(request):
    """Lista as especialidades ativas, ordenadas por campo 'ordem'."""
    especialidades = Especialidade.objects.filter(ativo=True).order_by('ordem', 'titulo')
    data = {
        'especialidades': [
            {
                'id': esp.pk,
                'titulo': esp.titulo,
                'slug': esp.slug,
                'descricao': esp.descricao,
                'imagem': request.build_absolute_uri(esp.imagem.url) if esp.imagem else '',
                'ordem': esp.ordem,
            }
            for esp in especialidades
        ]
    }

    return JsonResponse(data)


def detalhe_especialidade(request, slug):
    """Retorna os dados de uma especialidade ativa pelo seu slug."""
    try:
        esp = Especialidade.objects.get(slug=slug, ativo=True)
    except Especialidade.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Especialidade não encontrada'}, status=404)

    data = {
        'especialidade': {
            'id': esp.pk,
            'titulo': esp.titulo,
            'slug': esp.slug,
            'descricao': esp.descricao,
            'imagem': request.build_absolute_uri(esp.imagem.url) if esp.imagem else '',
            'ordem': esp.ordem,
        }
    }

    return JsonResponse(data)


def list_ebooks(request):
    """Lista os ebooks ativos, do mais recente ao mais antigo."""
    ebooks = Ebook.objects.filter(ativo=True).order_by('-data_criacao')

    data = {
        'ebooks': [
            {
                'titulo': ebook.titulo,
                'slug': ebook.slug,
                'descricao': ebook.descricao,
                'imagem_capa': request.build_absolute_uri(ebook.imagem_capa.url) if ebook.imagem_capa else '',
                'downloads': ebook.downloads,
            }
            for ebook in ebooks
        ]
    }

    return JsonResponse(data)


def baixar_ebook(request, slug):
    """Serve o arquivo do ebook e incrementa o contador de downloads."""
    ebook = get_object_or_404(Ebook, slug=slug, ativo=True)

    if not ebook.arquivo:
        return JsonResponse({'status': 'error', 'message': 'Arquivo indisponível no momento'}, status=404)

    Ebook.objects.filter(pk=ebook.pk).update(downloads=F('downloads') + 1)

    filename = Path(ebook.arquivo.name).name
    response = FileResponse(
        ebook.arquivo.open('rb'),
        as_attachment=True,
        filename=filename,
    )
    return response
