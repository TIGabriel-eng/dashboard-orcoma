"""
Vídeos privados servidos com link temporário.

O arquivo fica em PRIVATE_MEDIA_ROOT (fora de /media, que é público). Quem quer
tocar o vídeo pede um link ao endpoint de link; esse link é assinado e expira
em TEMPO_VALIDADE_SEGUNDOS. Depois disso, o mesmo endereço deixa de funcionar.
"""
import re
from pathlib import Path

from django.conf import settings
from django.core import signing
from django.http import FileResponse, HttpResponse, JsonResponse
from django.utils.http import urlencode

VIDEOS_PERMITIDOS = {'orcoma-day-bg.mp4'}
TEMPO_VALIDADE_SEGUNDOS = 60 * 60
# Tamanho máximo de cada pedaço enviado para navegadores que pedem "Range" (iPhone/Safari)
TAMANHO_MAXIMO_PEDACO = 2 * 1024 * 1024

_assinador = signing.TimestampSigner(salt='orcoma-video-link')


def link_video(request, nome):
    """Devolve um link temporário para o vídeo pedido."""
    if nome not in VIDEOS_PERMITIDOS:
        return JsonResponse({'status': 'error', 'message': 'Vídeo não encontrado'}, status=404)

    token = _assinador.sign(nome)
    url = request.build_absolute_uri('/api/video/stream/') + '?' + urlencode({'t': token})
    return JsonResponse({'status': 'ok', 'url': url})


def stream_video(request):
    """Entrega o vídeo se o link estiver válido e não tiver expirado."""
    token = request.GET.get('t', '')
    try:
        nome = _assinador.unsign(token, max_age=TEMPO_VALIDADE_SEGUNDOS)
    except signing.BadSignature:
        return JsonResponse({'status': 'error', 'message': 'Link expirado ou inválido'}, status=403)

    if nome not in VIDEOS_PERMITIDOS:
        return JsonResponse({'status': 'error', 'message': 'Vídeo não encontrado'}, status=404)

    caminho = Path(settings.PRIVATE_MEDIA_ROOT) / nome
    if not caminho.exists():
        return JsonResponse({'status': 'error', 'message': 'Vídeo não encontrado'}, status=404)

    return _resposta_com_range(request, caminho)


def _resposta_com_range(request, caminho):
    """Responde com suporte a 'Range', exigido pelo Safari para tocar vídeo."""
    tamanho = caminho.stat().st_size
    cabecalho = request.headers.get('Range')

    if not cabecalho:
        resposta = FileResponse(open(caminho, 'rb'), content_type='video/mp4')
        resposta['Accept-Ranges'] = 'bytes'
        return resposta

    partes = re.match(r'bytes=(\d*)-(\d*)$', cabecalho)
    if not partes:
        return HttpResponse(status=416, headers={'Content-Range': f'bytes */{tamanho}'})

    inicio_txt, fim_txt = partes.groups()
    if inicio_txt == '':
        # Pedido dos últimos N bytes
        inicio = max(tamanho - int(fim_txt), 0)
        fim = tamanho - 1
    else:
        inicio = int(inicio_txt)
        fim = int(fim_txt) if fim_txt else tamanho - 1

    fim = min(fim, tamanho - 1, inicio + TAMANHO_MAXIMO_PEDACO - 1)
    if inicio > fim:
        return HttpResponse(status=416, headers={'Content-Range': f'bytes */{tamanho}'})

    with open(caminho, 'rb') as arquivo:
        arquivo.seek(inicio)
        dados = arquivo.read(fim - inicio + 1)

    resposta = HttpResponse(dados, status=206, content_type='video/mp4')
    resposta['Content-Range'] = f'bytes {inicio}-{fim}/{tamanho}'
    resposta['Content-Length'] = str(len(dados))
    resposta['Accept-Ranges'] = 'bytes'
    return resposta
