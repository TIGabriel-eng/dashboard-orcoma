"""Suporte leve à proteção de formulários (honeypot, rate limit, reCAPTCHA).

A camada de monitoramento de segurança (SecurityEvent / IPSuspeito) foi
removida: Cloudflare e o reCAPTCHA do Google já cuidam disso. Este módulo
agora apenas expõe helpers que o fluxo anti-spam dos formulários chama,
sem gravar nada no banco.
"""
import logging

logger = logging.getLogger(__name__)


def get_client_ip(request):
    """Retorna o IP do visitante, respeitando proxies (X-Forwarded-For)."""
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '').strip()


def registrar_honeypot(request, ip=None):
    """Chamado quando o campo honeypot veio preenchido (bot confirmado).

    O bot é rejeitado pelo chamador (recebe sucesso falso, sem salvar os
    dados). Aqui nada é gravado.
    """
    logger.info('[form] Honeypot preenchido (bot descartado) IP=%s', ip or get_client_ip(request))


def registrar_rate_limit(request, ip=None):
    """Chamado quando o rate limit de contato é excedido."""
    logger.info('[form] Rate limit atingido IP=%s', ip or get_client_ip(request))


def registrar_falha_recaptcha(request, ip=None):
    """Chamado quando a verificação de reCAPTCHA falha."""
    logger.info('[form] reCAPTCHA inválido IP=%s', ip or get_client_ip(request))
