"""E-mails da newsletter: boas-vindas no cadastro e aviso de cada post publicado.

Todo e-mail traz um link para descadastrar. O link leva a pk da inscrição assinada
(django.core.signing), então o e-mail do assinante não aparece na URL.
"""
import logging

from django.conf import settings
from django.core import signing
from django.core.mail import EmailMessage, get_connection

logger = logging.getLogger(__name__)

SALT_DESCADASTRO = 'newsletter-descadastro'


def link_descadastro(inscricao):
    token = signing.dumps(inscricao.pk, salt=SALT_DESCADASTRO)
    return f"{settings.SITE_URL.rstrip('/')}/api/newsletter/descadastrar/?t={token}"


def _saudacao(inscricao):
    return f'Olá, {inscricao.nome}!' if inscricao.nome else 'Olá!'


def _mensagem(inscricao, assunto, corpo):
    return EmailMessage(
        subject=assunto,
        body=corpo,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[inscricao.email],
    )


def _enviar(mensagens):
    """Envia uma a uma: a falha em um e-mail não impede os demais."""
    with get_connection() as conexao:
        for msg in mensagens:
            msg.connection = conexao
            try:
                msg.send()
            except Exception:
                logger.exception('[Newsletter] falha ao enviar e-mail para %s', msg.to)


def enviar_boas_vindas(inscricao):
    corpo = (
        f"{_saudacao(inscricao)}\n\n"
        "Obrigado por assinar a newsletter da Orcoma. A partir de agora você recebe "
        "neste e-mail as novidades do nosso blog.\n\n"
        f"Para deixar de receber estes e-mails, acesse: {link_descadastro(inscricao)}\n\n"
        "Orcoma Contabilidade"
    )
    _enviar([_mensagem(inscricao, 'Bem-vindo à newsletter da Orcoma', corpo)])


def enviar_novo_post(post_pk):
    """Avisa todos os assinantes ativos sobre um post publicado."""
    from .models import NewsletterInscricao, PostBlog

    post = PostBlog.objects.filter(pk=post_pk, status='publicado').first()
    if post is None:
        return

    link = f"{settings.FRONTEND_URL.rstrip('/')}/#/blog-post/{post.slug}"
    mensagens = []
    for inscricao in NewsletterInscricao.objects.filter(ativo=True).iterator():
        resumo = f"{post.resumo}\n\n" if post.resumo else ''
        corpo = (
            f"{_saudacao(inscricao)}\n\n"
            "Publicamos um novo post no blog da Orcoma:\n\n"
            f"{post.titulo}\n\n"
            f"{resumo}"
            f"Leia agora: {link}\n\n"
            f"Para deixar de receber estes e-mails, acesse: {link_descadastro(inscricao)}\n\n"
            "Orcoma Contabilidade"
        )
        mensagens.append(_mensagem(inscricao, f'Novo no blog: {post.titulo}', corpo))
    _enviar(mensagens)
