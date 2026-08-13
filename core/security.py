"""Utilitários de monitoramento e segurança do site Orcoma.

Centraliza a detecção de comportamento suspeito, o registro de eventos
de segurança, a marcação de IPs suspeitos e o envio de alertas por e-mail.

IMPORTANTE: este módulo é 100% tolerante a falhas. Qualquer erro aqui é
capturado e logado — nunca derruba nem atrasa um request do site.
"""
import logging
import re

from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail

from .models import IPSuspeito, SecurityEvent

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Limites de detecção (ajuste fino conforme o tráfego do site)
# ---------------------------------------------------------------------------
REQ_RATE_WINDOW = 10          # janela de contagem em segundos
REQ_RATE_THRESHOLD = 40       # mais de X requisições na janela -> suspeito
ALERTA_EMAIL_INTERVALO = 3600  # suprime e-mails repetidos do mesmo IP+tipo (1 h)

# ---------------------------------------------------------------------------
# Assinaturas de comportamento suspeito
# ---------------------------------------------------------------------------
# Paths típicos de scanners/ataques (normalizados em minúsculas).
PATHS_ATACANTE = re.compile(
    r'(' + '|'.join([
        r'/\.env\b', r'/\.git', r'/\.svn', r'/\.hg\b', r'/\.aws\b',
        r'/\.ssh\b', r'/.composer', r'/.npmrc', r'/.htpasswd',
        r'wp-admin', r'wp-login', r'wp-content', r'wp-config', r'xmlrpc',
        r'/\w+\.php\b', r'/\w+\.asp\b', r'/\w+\.jsp\b', r'/\w+\.cgi',
        r'/\w+\.phtml', r'/\w+\.asa\b', r'/\w+\.config\b', r'/\w+\.old\b',
        r'/laravel', r'/phpmyadmin', r'/pma/', r'/actuator', r'/console',
        r'\.sql\b', r'\.bak\b', r'\.swp\b', r'\.dump\b', r'\.env\.php',
        r'c99', r'r57', r'webshell', r'shell\.php', r'cmd\.exe',
        r'/server-status', r'/server-info', r'/wordpress', r'/joomla',
        r'/drupal', r'/administrator', r'/api/v1/db', r'/gitea', r'/jenkins',
        r'/metrics', r'/swagger', r'/actuator/heapdump',
    ]) + ')',
    re.IGNORECASE,
)

# User-Agents de ferramentas de varredura/ataque ou de clientes não-navegador
# comumente abusados (crawlers maliciosos).
UA_SUSPEITO = re.compile(
    r'(' + '|'.join([
        r'sqlmap', r'nikto', r'nmap', r'nessus', r'openvas', r'wpscan',
        r'joomscan', r'acunetix', r'burp', r'zaproxy', r'owasp',
        r'python-requests', r'python-urllib', r'aiohttp', r'httpx',
        r'go-http-client', r'scrapy', r'zgrab', r'masscan', r'hydra',
        r'metasploit', r'fimap', r'sql-injector', r'dirbuster',
        r'gobuster', r'ffuf', r'jok3r', r'wpscanner',
    ]) + ')',
    re.IGNORECASE,
)

# Sinais de injeção (SQLi / XSS / path traversal / shell) na URL.
# Os padrões aceitam espaço literal ou codificado como URL (+, %20).
SINAIS_INJECAO = [
    r'union[\s+%20]*(all[\s+%20]*)?select',   # SQLi clássico (com/sem "all")
    r'/\*',
    r"'\s*or\s*'1'='1",
    r'\"\s*or\s*\"1\"=\"1',
    r'\bor[\s+%20]+1\b',
    r'\b(1|12)\s*=\s*(1|12)\b',
    r';[\s+%20]*drop[\s+%20]+table',
    r';[\s+%20]*insert[\s+%20]+into',
    r'<[\s+%20]*script',
    r'<script[\s+%20>]',
    r'javascript:',
    r'on[a-z]*\s*=',
    r'<iframe',
    r'etc/(passwd|shadow)',
    r'\.\.(?:/|%2f|\\\\|%5c)\.\.',
    r'%00',
    r'whoami',
    r'cat\s+/etc',
    r'curl\s+http',
    r'wget\s+http',
    r'eval\s*\(',
    r'base64_encode',
    r'cmd\.exe',
    r'\/proc\/self\/environ',
    r'phpinfo',
]
SINAIS_INJECAO_RE = re.compile('(' + '|'.join(SINAIS_INJECAO) + ')', re.IGNORECASE)

# IPs locais: em desenvolvimento o visitante é o próprio dono do site.
IPS_LOCAIS = {'127.0.0.1', '::1', '0.0.0.0'}

# Tipos de evento que merecem e-mail (evita spam para coisas menores).
TIPOS_QUE_ALERTAM = {
    'request_rate', 'path_invasivo', 'user_agent_suspeito',
    'injecao', 'honeypot', 'falha_recaptcha', 'rate_limit',
    'upload_invalido', 'login_admin',
}

# ---------------------------------------------------------------------------
# Registro e marcação
# ---------------------------------------------------------------------------
def get_client_ip(request):
    """Retorna o IP do visitante, respeitando proxies (X-Forwarded-For)."""
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '').strip()


def _is_local(ip):
    """IP local (desenvolvimento) não dispara alarmes."""
    return ip in IPS_LOCAIS or ip.startswith('127.') or ip == '::ffff:127.0.0.1'


def registrar_evento(tipo, ip, path='', user_agent='', detalhes=''):
    """Cria um SecurityEvent. Falhas são silenciadas."""
    try:
        SecurityEvent.objects.create(
            tipo=tipo,
            ip_address=ip or '0.0.0.0',
            path=(path or '')[:500],
            user_agent=(user_agent or '')[:500],
            detalhes=(detalhes or '')[:2000],
        )
    except Exception:
        logger.exception('[seguranca] Falha ao registrar evento de segurança')


def marcar_ip_suspeito(ip, motivo, nivel=2):
    """Marca um IP como suspeito (cria ou reativa o registro).

    Retorna True se o IP não estava marcado/ativo antes.
    """
    if not ip or _is_local(ip):
        return False
    try:
        obj, criado = IPSuspeito.objects.get_or_create(
            ip_address=ip,
            defaults={'motivo': motivo, 'nivel': nivel, 'resolvido': False},
        )
        if not criado:
            mudou = False
            if obj.resolvido:
                obj.resolvido = False
                mudou = True
            if motivo not in (obj.motivo or ''):
                obj.motivo = ((obj.motivo or '') + '\n' + motivo).strip()
                mudou = True
            if mudou:
                obj.save(update_fields=['motivo', 'resolvido', 'ultima_visto'])
        return True
    except Exception:
        logger.exception('[seguranca] Falha ao marcar IP suspeito: %s', ip)
        return False


def ip_e_suspeito(ip):
    """True se o IP está marcado como suspeito e ainda não resolvido."""
    if not ip:
        return False
    try:
        return IPSuspeito.objects.filter(ip_address=ip, resolvido=False).exists()
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Alerta por e-mail
# ---------------------------------------------------------------------------
def enviar_alerta(tipo, ip='', path='', user_agent='', motivo='', detalhes=''):
    """Envia e-mail de alerta (se configurado), com supressão por IP+tipo.

    Sem ALERT_EMAIL_TO no .env, apenas registra um log de warning — o
    evento continua visível no painel administrativo.
    """
    if tipo not in TIPOS_QUE_ALERTAM:
        return
    try:
        to = getattr(settings, 'ALERT_EMAIL_TO', '').strip()
        chave = f'sec_alerta:{ip or "vazio"}:{tipo}'
        ja_enviado = cache.get(chave)

        if not to:
            # Sem e-mail configurado: loga para trilha de auditoria.
            if not ja_enviado:
                cache.set(chave, True, ALERTA_EMAIL_INTERVALO)
                logger.warning(
                    '[seguranca] ALERTA %s IP=%s path=%s motivo=%s',
                    tipo, ip, path, (motivo or detalhes)[:200],
                )
            return

        if ja_enviado:
            return  # já alertamos este IP+tipo recentemente
        cache.set(chave, True, ALERTA_EMAIL_INTERVALO)

        base_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')
        assunto = f'[Orcoma Segurança] {tipo} - IP {ip}'
        corpo = (
            f'Foi detectada atividade suspeita no site Orcoma.\n\n'
            f'Tipo: {tipo}\n'
            f'IP: {ip}\n'
            f'Path: {path}\n'
            f'User-Agent: {user_agent}\n'
            f'Motivo: {motivo}\n'
            f'Detalhes: {detalhes}\n\n'
            f'Acesse o painel para investigar:\n'
            f'{base_url}/admin/core/securityevent/\n'
            f'{base_url}/admin/core/ipsuspeito/\n'
        )
        send_mail(
            assunto,
            corpo,
            getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@orcoma.com.br'),
            [to],
            fail_silently=True,
        )
    except Exception:
        logger.exception('[seguranca] Falha ao enviar alerta de e-mail')
# ---------------------------------------------------------------------------
# Detecção automática (chamada pelo middleware em todo request)
# ---------------------------------------------------------------------------
def monitorar_request(request):
    """Analisa um request e reage a sinais de ataque.

    Nunca bloqueia: apenas registra evento, marca o IP e (eventualmente)
    envia alerta por e-mail. É tolerante a falhas: não deve nunca quebrar
    o fluxo normal do site.
    """
    path = request.path
    if path.startswith(('/static/', '/media/', '/favicon')):
        return

    ip = get_client_ip(request)
    user_agent = request.META.get('HTTP_USER_AGENT', '')

    # 1) Sinais de injeção na URL (path + query string)
    url_alvo = path.lower() + ('?' + request.GET.urlencode() if request.GET else '')
    m_inj = SINAIS_INJECAO_RE.search(url_alvo)
    if m_inj:
        _reagir('injecao', ip, path, user_agent,
                motivo=f'Sinais de injeção na URL: {m_inj.group(0)!r}',
                detalhes=url_alvo[:500], nivel=3)
        return  # já marcou; evita cascata de regras

    # 2) Path de scanner/ataque conhecido
    if PATHS_ATACANTE.search(path):
        _reagir('path_invasivo', ip, path, user_agent,
                motivo='Acesso a caminho típico de ataque/scanner',
                detalhes=path[:500], nivel=2)
        return

    # 3) User-Agent de ferramenta de ataque
    m_ua = UA_SUSPEITO.search(user_agent or '')
    if m_ua:
        _reagir('user_agent_suspeito', ip, path, user_agent,
                motivo=f'User-Agent de ferramenta de ataque: {m_ua.group(0)!r}',
                detalhes=(user_agent or '')[:500], nivel=2)
        return

    # 4) Taxa alta de requisições no mesmo IP (janela curta)
    if ip and not _is_local(ip):
        try:
            chave = f'sec_req_rate:{ip}'
            contador = cache.get(chave, 0)
            if contador == 0:
                cache.set(chave, 1, REQ_RATE_WINDOW)
            else:
                cache.set(chave, contador + 1, REQ_RATE_WINDOW)
            if contador + 1 >= REQ_RATE_THRESHOLD:
                _reagir('request_rate', ip, path, user_agent,
                        motivo=f'{contador + 1} requisições em {REQ_RATE_WINDOW}s',
                        detalhes=path[:500], nivel=2)
        except Exception:
            pass


def _reagir(tipo, ip, path, user_agent, motivo, detalhes, nivel=2):
    """Registra o evento, marca o IP e dispara alerta, sem quebrar nada."""
    registrar_evento(tipo, ip or '', path, user_agent, f'{motivo} — {detalhes}')
    marcar_ip_suspeito(ip, f'[{tipo}] {motivo}', nivel=nivel)
    enviar_alerta(tipo, ip=ip, path=path, user_agent=user_agent,
                  motivo=motivo, detalhes=detalhes)


# ---------------------------------------------------------------------------
# Hooks chamados pelos views de formulário (honeypot/rate limit/recaptcha)
# ---------------------------------------------------------------------------
def registrar_honeypot(request, ip=None):
    """Chamado quando o campo honeypot veio preenchido (bot confirmado)."""
    ip = ip or get_client_ip(request)
    ua = request.META.get('HTTP_USER_AGENT', '')
    _reagir('honeypot', ip, request.path, ua,
            motivo='Campo honeypot preenchido (bot detectado)',
            detalhes='O formulário respondeu sucesso, mas nenhum dado foi salvo.',
            nivel=2)


def registrar_rate_limit(request, ip=None):
    """Chamado quando o rate limit de contato é excedido."""
    ip = ip or get_client_ip(request)
    ua = request.META.get('HTTP_USER_AGENT', '')
    _reagir('rate_limit', ip, request.path, ua,
            motivo='Limite de requisições de contato excedido (possível flood)',
            detalhes='Requisição rejeitada com HTTP 429.',
            nivel=2)


def registrar_falha_recaptcha(request, ip=None):
    """Chamado quando a verificação de reCAPTCHA falha."""
    ip = ip or get_client_ip(request)
    ua = request.META.get('HTTP_USER_AGENT', '')
    _reagir('falha_recaptcha', ip, request.path, ua,
            motivo='reCAPTCHA inválido',
            detalhes='Provável automação tentando usar formulário protegido.',
            nivel=1)