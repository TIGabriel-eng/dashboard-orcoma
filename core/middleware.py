"""Middleware de monitoramento de segurança.

Observa cada request em busca de sinais de ataque (scanners, injeção,
bot, flood) e registra os eventos. Nunca bloqueia nem modifica requests;
uma falha aqui nunca derruba o site.
"""
import logging

from . import security

logger = logging.getLogger(__name__)


class SegurancaMonitorMiddleware:
    """Inspeciona cada request e reage a comportamento suspeito."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            security.monitorar_request(request)
        except Exception:
            logger.exception('[seguranca] Falha no middleware de monitoramento')
        return self.get_response(request)