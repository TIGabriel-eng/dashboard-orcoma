"""Cria ou atualiza o superusuário admin a partir das variáveis de ambiente.

Uso (ex.: Release Command no Render):
    python manage.py criar_superusuario

Variáveis lidas:
    ADMIN_USERNAME, ADMIN_PASSWORD, ADMIN_EMAIL
"""
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Cria ou atualiza o superusuário admin via variáveis de ambiente.'

    def handle(self, *args, **options):
        username = os.environ.get('ADMIN_USERNAME', '').strip()
        password = os.environ.get('ADMIN_PASSWORD', '').strip()
        email = os.environ.get('ADMIN_EMAIL', '').strip()

        if not username or not password:
            self.stdout.write(self.style.WARNING(
                'ADMIN_USERNAME/ADMIN_PASSWORD não definidos; nenhum superusuário criado.'
            ))
            return

        User = get_user_model()
        user, criado = User.objects.get_or_create(
            username=username,
            defaults={
                'email': email,
                'cargo': 'admin',
                'is_staff': True,
                'is_superuser': True,
            },
        )
        if not criado:
            user.email = email or user.email
            user.cargo = 'admin'
            user.is_staff = True
            user.is_superuser = True

        user.set_password(password)
        user.save()

        self.stdout.write(self.style.SUCCESS(
            f'Superusuário "{username}" {"criado" if criado else "atualizado"} com sucesso.'
        ))
