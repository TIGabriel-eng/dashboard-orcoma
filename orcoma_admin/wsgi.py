"""
WSGI config for orcoma_admin project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'orcoma_admin.settings')

application = get_wsgi_application()

from django.core.management import call_command
# Garante o schema mesmo quando o Render não roda o Procfile (Start Command padrão).
call_command('migrate', '--noinput', verbosity=0)
call_command('collectstatic', '--noinput', verbosity=0)
call_command('criar_superusuario', verbosity=0)
