from django.conf import settings
from django.http import HttpResponse, Http404
from pathlib import Path


def frontend_index(request):
    """Serve the built Vite frontend (dist/index.html)."""
    index_path = Path(settings.FRONTEND_DIST_DIR) / 'index.html'
    if not index_path.exists():
        raise Http404(
            'Frontend não compilado. Execute "npm run build" na raiz do projeto '
            'para gerar o diretório dist/.'
        )
    with index_path.open('rb') as f:
        return HttpResponse(f.read(), content_type='text/html; charset=utf-8')