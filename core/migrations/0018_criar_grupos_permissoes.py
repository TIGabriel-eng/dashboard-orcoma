# Cria os grupos de acesso do admin (Social Media / RH / Comercial) e suas
# permissões de modelo. Idempotente: re-executar apenas redefine as permissões
# conforme o mapeamento abaixo (fonte da verdade).
#
# Admin não vira grupo: usa is_superuser (vê tudo).

from django.db import migrations

GRUPOS = {
    'social_media': {
        'nome': 'Social Media',
        'modelos': [
            'postblog', 'ebook', 'evento', 'especialidade',
            'carrossel', 'sobrenosfoto', 'pageview',
        ],
    },
    'rh': {
        'nome': 'RH',
        'modelos': ['jobapplication'],
    },
    'comercial': {
        'nome': 'Comercial',
        'modelos': ['contactlead', 'cliente', 'pageview', 'newsletterinscricao'],
    },
}

VERBOS = ('add', 'change', 'delete', 'view')


def criar_grupos(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')
    ContentType = apps.get_model('contenttypes', 'ContentType')
    db_alias = schema_editor.connection.alias

    for cfg in GRUPOS.values():
        grupo, _ = Group.objects.using(db_alias).get_or_create(name=cfg['nome'])
        grupo.permissions.clear()
        codenames = set()
        for modelo in cfg['modelos']:
            for verbo in VERBOS:
                codenames.add(f'{verbo}_{modelo}')
        perms = Permission.objects.using(db_alias).filter(
            content_type__app_label='core',
            codename__in=codenames,
        )
        grupo.permissions.add(*perms)


def sem_reversa(apps, schema_editor):
    """Reversão segura: não apaga grupos nem permissões já concedidas."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0017_alter_usuario_cargo'),
    ]

    operations = [
        migrations.RunPython(criar_grupos, sem_reversa),
    ]
