"""Envio de leads para o WhatsApp via WhatsApp Cloud API (Meta).

As credenciais vêm de settings.WHATSAPP_* (carregadas do arquivo .env).
Nenhuma chave fica hardcoded neste código.
"""
import json
import logging
import urllib.error
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)

GRAPH_API_URL = 'https://graph.facebook.com/v21.0/{phone_number_id}/messages'


def _sanitize(value) -> str:
    return (value or '').strip()


def _template_components(dados) -> list:
    """Parâmetros do template na ordem definida no painel do WhatsApp (Meta)."""
    return [
        {
            'type': 'body',
            'parameters': [
                {'type': 'text', 'text': _sanitize(dados.get('nome'))},
                {'type': 'text', 'text': _sanitize(dados.get('celular'))},
                {'type': 'text', 'text': _sanitize(dados.get('email'))},
                {'type': 'text', 'text': _sanitize(dados.get('cnpj')) or '-'},
            ],
        }
    ]


def send_lead_to_whatsapp(dados) -> bool:
    """Envia os dados do lead para o WhatsApp do Gilton Comercial.

    Sem credenciais configuradas, apenas registra a mensagem que seria enviada
    e retorna False (o fluxo da API continua funcionando).
    """
    token = settings.WHATSAPP_TOKEN.strip()
    phone_number_id = settings.WHATSAPP_PHONE_NUMBER_ID.strip()
    template_name = settings.WHATSAPP_TEMPLATE_NAME.strip()
    to_number = settings.WHATSAPP_TO.strip()

    if not (token and phone_number_id and template_name and to_number):
        logger.warning(
            '[WhatsApp] Credenciais nao configuradas. Mensagem que seria enviada: %s',
            json.dumps(dados, ensure_ascii=False),
        )
        return False

    url = GRAPH_API_URL.format(phone_number_id=phone_number_id)
    payload = {
        'messaging_product': 'whatsapp',
        'to': to_number,
        'type': 'template',
        'template': {
            'name': template_name,
            'language': {'code': 'pt_BR'},
            'components': _template_components(dados),
        },
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        method='POST',
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            response_body = resp.read().decode('utf-8')
            logger.info('[WhatsApp] Mensagem enviada: %s', response_body)
            return True
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode('utf-8', errors='replace')
        logger.error('[WhatsApp] Erro HTTP %s ao enviar: %s', exc.code, error_body)
        return False
    except urllib.error.URLError as exc:
        logger.error('[WhatsApp] Falha de rede ao enviar: %s', exc.reason)
        return False
