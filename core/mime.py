"""Helper para detectar content-type, incluindo extensões comuns da web."""

import mimetypes
import os

# Extensões que o `mimetypes` do Windows/Unix nem sempre reconhece.
EXTRA_CONTENT_TYPES = {
    '.webp': 'image/webp',
    '.avif': 'image/avif',
    '.svg': 'image/svg+xml',
    '.woff': 'font/woff',
    '.woff2': 'font/woff2',
    '.webm': 'video/webm',
    '.mov': 'video/quicktime',
}


def guess_content_type(name):
    content_type, _ = mimetypes.guess_type(name)
    if content_type:
        return content_type
    _, ext = os.path.splitext(name.lower())
    return EXTRA_CONTENT_TYPES.get(ext, 'application/octet-stream')