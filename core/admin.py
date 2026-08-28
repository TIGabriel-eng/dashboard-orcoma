from django.contrib import admin
from django.contrib.admin import AdminSite
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.http import HttpResponseForbidden
from django.utils.translation import gettext_lazy as _
from django.urls import path
from django.shortcuts import render
from django.db.models import Count, Sum
from django.utils import timezone
from django.utils.html import format_html, mark_safe
from datetime import timedelta

from .models import Usuario, PostBlog, Ebook, Evento, PageView, ContactLead, JobApplication, Especialidade, NewsletterInscricao, Carrossel, SobreNosFoto, Cliente
from django.db.models.functions import TruncDay, Lower
from django.db.models import Count
from collections import defaultdict
import json


# ---------------------------------------------------------------
# Cargos / grupos de acesso (base das permissões do admin)
# ---------------------------------------------------------------

VERBOS_PERMISSAO = ('add', 'change', 'delete', 'view')

# cargo (Usuario.cargo) -> nome do grupo Django
GRUPO_CARGO = {
    'social_media': 'Social Media',
    'rh': 'RH',
    'comercial': 'Comercial',
}

# nome do grupo -> modelos sob gestão desse grupo
GRUPO_PERMISSOES = {
    'Social Media': [
        'postblog', 'ebook', 'evento', 'especialidade',
        'carrossel', 'sobrenosfoto', 'pageview',
    ],
    'RH': ['jobapplication'],
    'Comercial': ['contactlead', 'cliente', 'pageview', 'newsletterinscricao'],
}


def _garantir_grupos():
    """Garante que os grupos de acesso existam com as permissões corretas.

    Idempotente: chamado ao salvar um usuário, mantém os grupos sempre
    sincronizados com o mapeamento acima (fonte da verdade no código).
    """
    for nome, modelos in GRUPO_PERMISSOES.items():
        grupo, _ = Group.objects.get_or_create(name=nome)
        codenames = {
            f'{verbo}_{modelo}'
            for modelo in modelos
            for verbo in VERBOS_PERMISSAO
        }
        grupo.permissions.set(
            Permission.objects.filter(
                content_type__app_label='core',
                codename__in=codenames,
            )
        )


def _perfis_usuario(user):
    """Retorna o que o usuário pode ver no admin, baseado nas permissões."""
    def tem(*perms):
        return any(user.has_perm(f'core.{p}') for p in perms)

    return {
        'pode_gestao': tem(
            'view_postblog', 'view_ebook', 'view_evento',
            'view_especialidade', 'view_carrossel', 'view_sobrenosfoto',
        ),
        'pode_acessos': tem('view_pageview'),
        'pode_comercial': tem('view_contactlead', 'view_cliente', 'view_newsletterinscricao'),
        'pode_rh': tem('view_jobapplication'),
        'pode_usuarios': user.is_superuser or tem('view_usuario', 'change_usuario'),
    }


def _aplicar_cargo(user):
    """Sincroniza o cargo do usuário com grupo / is_staff / is_superuser.

    'admin' vira superuser (enxerga tudo). Cargos legados ou vazios não
    são alterados automaticamente.
    """
    cargo = user.cargo
    if cargo == 'admin':
        user.is_staff = True
        user.is_superuser = True
        user.groups.clear()
        user.save(update_fields=['is_staff', 'is_superuser'])
        return
    nome_grupo = GRUPO_CARGO.get(cargo)
    if nome_grupo is None:
        return
    _garantir_grupos()
    user.is_staff = True
    user.is_superuser = False
    user.groups.set(Group.objects.filter(name=nome_grupo))
    user.save(update_fields=['is_staff', 'is_superuser'])


class OrcomaAdminSite(AdminSite):
    site_header = 'Grupo Orcoma - Administração'
    site_title = 'Painel Administrativo'
    index_title = 'Dashboard'
    index_template = 'admin/dashboard.html'
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('', self.admin_view(self.dashboard_view), name='index'),
            path('comercial/', self.admin_view(self.comercial_dashboard_view), name='comercial'),
        ]
        return custom_urls + urls
    
    def _get_period_filter(self, request, param_name='periodo'):
        """Retorna filtro de data baseado no parâmetro 'periodo' da URL"""
        periodo = request.GET.get(param_name, 'mes')
        now = timezone.now()
        
        if periodo == 'dia':
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif periodo == 'semana':
            start = now - timedelta(days=now.weekday())
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        elif periodo == 'ano':
            start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        else:  # mês
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        return start, now, periodo

    def dashboard_view(self, request):
        # Perfil de acesso do usuário (definido pelos grupos/cargos)
        perfil = _perfis_usuario(request.user)
        pode_gestao = perfil['pode_gestao']
        pode_acessos = perfil['pode_acessos']
        pode_comercial = perfil['pode_comercial']
        pode_rh = perfil['pode_rh']
        pode_usuarios = perfil['pode_usuarios']

        # Estatísticas para o dashboard
        total_usuarios = Usuario.objects.count() if pode_usuarios else 0
        if pode_gestao:
            total_postagens = PostBlog.objects.filter(status='publicado').count()
            total_downloads = Ebook.objects.aggregate(total=Sum('downloads'))['total'] or 0
            total_eventos = Evento.objects.filter(data_inicio__gte=timezone.now()).count()
        else:
            total_postagens = 0
            total_downloads = 0
            total_eventos = 0

        # == Filtro por período ==
        periodo_atual = request.GET.get('periodo', 'mes')
        periodos_disponiveis = [
            {'key': 'dia', 'label': 'Dia'},
            {'key': 'semana', 'label': 'Semana'},
            {'key': 'mes', 'label': 'Mês'},
            {'key': 'ano', 'label': 'Ano'},
        ]

        start, end, _ = self._get_period_filter(request)
        periodo_duracao = end - start
        periodo_anterior_start = start - periodo_duracao

        # == Estatísticas de Acessos (PageView) ==
        if pode_acessos:
            total_acessos = PageView.objects.count()
            acessos_periodo = PageView.objects.filter(timestamp__gte=start, timestamp__lte=end).count()

            acessos_periodo_anterior = PageView.objects.filter(
                timestamp__gte=periodo_anterior_start, timestamp__lt=start
            ).count()

            if acessos_periodo_anterior > 0:
                variacao_acessos = round((acessos_periodo - acessos_periodo_anterior) / acessos_periodo_anterior * 100)
            else:
                variacao_acessos = 100 if acessos_periodo > 0 else 0

            acessos_por_dia = (
                PageView.objects
                .filter(timestamp__gte=start, timestamp__lte=end)
                .annotate(dia=TruncDay('timestamp'))
                .values('dia')
                .annotate(total=Count('id'))
                .order_by('dia')
            )
            acessos_chart_labels = [a['dia'].strftime('%d/%m') for a in acessos_por_dia]
            acessos_chart_data = [a['total'] for a in acessos_por_dia]
        else:
            total_acessos = 0
            acessos_periodo = 0
            variacao_acessos = 0
            acessos_chart_labels = []
            acessos_chart_data = []

        # == Estatísticas de Contato (ContactLead) ==
        if pode_comercial:
            total_contatos = ContactLead.objects.count()
            contatos_periodo = ContactLead.objects.filter(timestamp__gte=start, timestamp__lte=end).count()
            contatos_periodo_anterior = ContactLead.objects.filter(
                timestamp__gte=periodo_anterior_start, timestamp__lt=start
            ).count()
            if contatos_periodo_anterior > 0:
                variacao_contatos = round((contatos_periodo - contatos_periodo_anterior) / contatos_periodo_anterior * 100)
            else:
                variacao_contatos = 100 if contatos_periodo > 0 else 0

            contatos_recentes = ContactLead.objects.all().order_by('-timestamp')[:10]
        else:
            total_contatos = 0
            contatos_periodo = 0
            variacao_contatos = 0
            contatos_recentes = ContactLead.objects.none()

        # == Estatísticas de Candidaturas (JobApplication) ==
        if pode_rh:
            total_candidaturas = JobApplication.objects.count()
            candidaturas_periodo = JobApplication.objects.filter(timestamp__gte=start, timestamp__lte=end).count()
            candidaturas_periodo_anterior = JobApplication.objects.filter(
                timestamp__gte=periodo_anterior_start, timestamp__lt=start
            ).count()
            if candidaturas_periodo_anterior > 0:
                variacao_candidaturas = round((candidaturas_periodo - candidaturas_periodo_anterior) / candidaturas_periodo_anterior * 100)
            else:
                variacao_candidaturas = 100 if candidaturas_periodo > 0 else 0

            candidaturas_recentes = JobApplication.objects.all().order_by('-timestamp')[:10]
        else:
            total_candidaturas = 0
            candidaturas_periodo = 0
            variacao_candidaturas = 0
            candidaturas_recentes = JobApplication.objects.none()

        # Usuários recentes (últimos 5) — somente admin
        usuarios_recentes = (
            Usuario.objects.all().order_by('-date_joined')[:5]
            if pode_usuarios else Usuario.objects.none()
        )

        # Conteúdo de Gestão
        if pode_gestao:
            posts_recentes = PostBlog.objects.filter(status='publicado').order_by('-data_publicacao')[:5]
            ebooks_populares = Ebook.objects.filter(ativo=True).order_by('-downloads')[:5]
            proximos_eventos = Evento.objects.filter(
                data_inicio__gte=timezone.now(),
                ativo=True
            ).order_by('data_inicio')[:5]
        else:
            posts_recentes = PostBlog.objects.none()
            ebooks_populares = Ebook.objects.none()
            proximos_eventos = Evento.objects.none()

        # Indicador de tendência
        def sinal(v):
            if v > 0: return 'up'
            if v < 0: return 'down'
            return 'neutral'

        context = {
            **self.each_context(request),
            # Perfis de acesso (usados no template para esconder seções)
            'pode_gestao': pode_gestao,
            'pode_acessos': pode_acessos,
            'pode_comercial': pode_comercial,
            'pode_rh': pode_rh,
            'pode_usuarios': pode_usuarios,
            # Totais
            'total_usuarios': total_usuarios,
            'total_postagens': total_postagens,
            'total_downloads': total_downloads,
            'total_eventos': total_eventos,
            'usuarios_recentes': usuarios_recentes,
            'posts_recentes': posts_recentes,
            'ebooks_populares': ebooks_populares,
            'proximos_eventos': proximos_eventos,
            # Acessos
            'total_acessos': total_acessos,
            'acessos_periodo': acessos_periodo,
            'variacao_acessos': variacao_acessos,
            'sinal_acessos': sinal(variacao_acessos),
            'acessos_chart_labels': json.dumps(acessos_chart_labels),
            'acessos_chart_data': json.dumps(acessos_chart_data),
            # Contatos
            'total_contatos': total_contatos,
            'contatos_periodo': contatos_periodo,
            'variacao_contatos': variacao_contatos,
            'sinal_contatos': sinal(variacao_contatos),
            'contatos_recentes': contatos_recentes,
            # Candidaturas
            'total_candidaturas': total_candidaturas,
            'candidaturas_periodo': candidaturas_periodo,
            'variacao_candidaturas': variacao_candidaturas,
            'sinal_candidaturas': sinal(variacao_candidaturas),
            'candidaturas_recentes': candidaturas_recentes,
            # Filtro
            'periodo_atual': periodo_atual,
            'periodos_disponiveis': periodos_disponiveis,
            'title': 'Dashboard',
        }

        return render(request, 'admin/dashboard.html', context)

    def comercial_dashboard_view(self, request):
        """Dashboard Comercial: relatório de todas as formas de contato do site.

        Acesso restrito ao perfil Comercial (e admin/superuser).
        """
        if not (request.user.is_superuser or _perfis_usuario(request.user)['pode_comercial']):
            return HttpResponseForbidden('Você não tem permissão para acessar o Dashboard Comercial.')

        # Marco inicial: primeiro registro de contato (o banco só existe desde o novo site)
        primeiro_contato = ContactLead.objects.order_by('timestamp').first()
        data_inicio = primeiro_contato.timestamp if primeiro_contato else None

        leads = ContactLead.objects.all()
        total_contatos = leads.count()

        # Pessoas = contatos com e-mail/celular identificado (cliques de WhatsApp ficam de fora)
        com_identidade = leads.exclude(email='').exclude(email__isnull=True)
        total_pessoas = com_identidade.annotate(email_lower=Lower('email')).values('email_lower').distinct().count()
        celulares_identificados = leads.filter(email__exact='').exclude(celular__exact='')
        total_pessoas += celulares_identificados.values('celular').distinct().count()

        # Contatos por origem e por interesse
        por_origem = list(
            leads.values('origem')
            .annotate(total=Count('id'))
            .order_by('-total')
        )
        origem_choices = dict(ContactLead.ORIGEM_CHOICES)
        for item in por_origem:
            item['label'] = origem_choices.get(item['origem'], item['origem'])

        por_interesse = list(
            leads.values('interesse')
            .annotate(total=Count('id'))
            .order_by('-total')
        )
        interesse_choices = dict(ContactLead.INTERESSE_CHOICES)
        for item in por_interesse:
            item['label'] = interesse_choices.get(item['interesse'], item['interesse'])

        # Quantas vezes cada pessoa entrou em contato (ranking)
        ranking_por_email = (
            com_identidade.annotate(chave=Lower('email'))
            .values('chave', 'email')
            .annotate(total=Count('id'))
            .order_by('-total', 'email')
        )
        ranking_por_celular = (
            celulares_identificados.values('celular')
            .annotate(total=Count('id'))
            .order_by('-total', 'celular')
        )
        ranking = [
            {'chave': item['email'], 'total': item['total']}
            for item in ranking_por_email[:15]
        ]
        ranking += [
            {'chave': f"Celular {item['celular']}", 'total': item['total']}
            for item in ranking_por_celular[:15]
        ]
        ranking.sort(key=lambda r: r['total'], reverse=True)
        ranking = ranking[:15]

        ultimos_contatos = leads.order_by('-timestamp')[:15]

        # Newsletter (outra forma de contato do site, não RH)
        total_newsletter = NewsletterInscricao.objects.count()
        newsletter_recentes = NewsletterInscricao.objects.all().order_by('-data_criacao')[:10]

        context = {
            **self.each_context(request),
            'title': 'Dashboard Comercial',
            'data_inicio': data_inicio,
            'total_contatos': total_contatos,
            'total_pessoas': total_pessoas,
            'total_newsletter': total_newsletter,
            'por_origem': por_origem,
            'por_interesse': por_interesse,
            'ranking': ranking,
            'ultimos_contatos': ultimos_contatos,
            'newsletter_recentes': newsletter_recentes,
        }

        return render(request, 'admin/comercial.html', context)


# Instância do admin customizado
admin_site = OrcomaAdminSite(name='orcoma_admin')


class UsuarioAdmin(admin.ModelAdmin):
    list_display = ['username', 'get_full_name', 'email', 'cargo', 'is_active', 'last_login', 'date_joined']
    list_filter = ['cargo', 'is_active', 'date_joined']
    search_fields = ['username', 'first_name', 'last_name', 'email']
    # list_editable removido — template custom não renderiza campos de formulário
    readonly_fields = ['last_login', 'date_joined']
    fieldsets = (
        ('Informações de Login', {
            'fields': ('username', 'email', 'password')
        }),
        ('Informações Pessoais', {
            'fields': ('first_name', 'last_name', 'telefone', 'avatar')
        }),
        ('Permissões', {
            'fields': ('cargo', 'is_active', 'is_superuser'),
            'description': 'O cargo define as permissões automaticamente: Admin vê tudo; Social Media vê Gestão e acessos; RH vê candidaturas; Comercial vê leads, clientes e métricas. Cargos legados (Editor/Moderador) não recebem permissões automáticas.',
        }),
        ('Datas', {
            'fields': ('last_login', 'date_joined')
        }),
    )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        _aplicar_cargo(obj)
        obj.save()


class PostBlogAdmin(admin.ModelAdmin):
    list_display = ['imagem_thumbnail', 'titulo', 'autor', 'status', 'data_publicacao', 'visualizacoes']
    list_display_links = ['titulo']
    list_filter = ['status', 'data_criacao', 'autor']
    search_fields = ['titulo', 'conteudo', 'autor__username']
    prepopulated_fields = {'slug': ('titulo',)}
    readonly_fields = ['data_criacao', 'visualizacoes']
    fieldsets = (
        ('Conteúdo', {
            'fields': ('titulo', 'slug', 'resumo', 'conteudo', 'imagem_destaque')
        }),
        ('Publicação', {
            'fields': ('autor', 'status', 'data_publicacao'),
            'description': 'A data de publicação é exibida no card do blog no site. Deixe em branco para usar a data atual ao publicar.',
        }),
        ('Estatísticas', {
            'fields': ('visualizacoes', 'data_criacao')
        }),
    )

    def imagem_thumbnail(self, obj):
        if obj.imagem_destaque:
            return format_html(
                '<img src="{}" width="90" height="55" style="object-fit:cover;border-radius:6px;" />',
                obj.imagem_destaque.url,
            )
        return '-'
    imagem_thumbnail.short_description = 'Imagem'


class EbookAdmin(admin.ModelAdmin):
    list_display = ['titulo', 'downloads', 'ativo', 'data_criacao']
    list_filter = ['ativo', 'data_criacao']
    search_fields = ['titulo', 'descricao']
    prepopulated_fields = {'slug': ('titulo',)}
    readonly_fields = ['downloads', 'data_criacao']
    fieldsets = (
        ('Informações do Ebook', {
            'fields': ('titulo', 'slug', 'descricao', 'arquivo', 'imagem_capa')
        }),
        ('Configurações', {
            'fields': ('downloads', 'ativo', 'data_criacao')
        }),
    )


class PageViewAdmin(admin.ModelAdmin):
    list_display = ['path', 'ip_address', 'user_agent', 'timestamp']
    list_filter = ['timestamp']
    search_fields = ['path', 'ip_address', 'user_agent']
    readonly_fields = ['path', 'ip_address', 'user_agent', 'timestamp']
    list_per_page = 100


class ContactLeadAdmin(admin.ModelAdmin):
    list_display = ['nome', 'email', 'celular', 'cpf', 'cnpj', 'origem', 'interesse', 'timestamp']
    list_filter = ['origem', 'interesse', 'timestamp']
    search_fields = ['nome', 'email', 'celular', 'cpf']
    readonly_fields = ['nome', 'email', 'celular', 'cpf', 'cnpj', 'mensagem', 'origem', 'interesse', 'timestamp']


class JobApplicationAdmin(admin.ModelAdmin):
    list_display = ['imagem_curriculo', 'nome', 'email', 'telefone', 'timestamp']
    list_filter = ['timestamp']
    search_fields = ['nome', 'email']
    readonly_fields = ['nome', 'email', 'telefone', 'mensagem', 'curriculo', 'preview_display', 'timestamp']
    fieldsets = (
        ('Candidato', {
            'fields': ('nome', 'email', 'telefone')
        }),
        ('Currículo', {
            'fields': ('curriculo', 'preview_display')
        }),
        ('Mensagem', {
            'fields': ('mensagem',)
        }),
        ('Dados', {
            'fields': ('timestamp',)
        }),
    )

    def has_add_permission(self, request):
        return False

    def delete_model(self, request, obj):
        self._remove_arquivos(obj)
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            self._remove_arquivos(obj)
        super().delete_queryset(request, queryset)

    @staticmethod
    def _remove_arquivos(obj):
        if obj.curriculo:
            obj.curriculo.delete(save=False)
        if obj.preview:
            obj.preview.delete(save=False)

    def imagem_curriculo(self, obj):
        if obj.preview:
            return format_html(
                '<img src="{}" width="90" height="55" style="object-fit:cover;border-radius:6px;" />',
                obj.preview.url,
            )
        if obj.curriculo:
            ext = obj.curriculo.name.rsplit('.', 1)[-1].lower() if '.' in obj.curriculo.name else ''
            return format_html(
                '<span style="font-size:11px;font-weight:700;color:#666;background:#eee;padding:4px 10px;border-radius:999px;">.{}</span>',
                ext or 'arquivo',
            )
        return '-'
    imagem_curriculo.short_description = 'Currículo'

    def preview_display(self, obj):
        if obj.preview:
            return format_html(
                '<img src="{}" style="max-width:260px;border-radius:8px;box-shadow:0 1px 4px rgba(0,0,0,0.15);" />',
                obj.preview.url,
            )
        return '-'
    preview_display.short_description = 'Prévia da primeira página'


class EventoAdmin(admin.ModelAdmin):
    list_display = ['imagem_thumbnail', 'titulo', 'data_inicio', 'local', 'ativo', 'is_upcoming']
    list_display_links = ['titulo']
    list_filter = ['ativo', 'data_inicio']
    search_fields = ['titulo', 'descricao', 'local']
    prepopulated_fields = {'slug': ('titulo',)}
    readonly_fields = ['data_criacao', 'is_upcoming']
    fieldsets = (
        ('Informações do Evento', {
            'fields': ('titulo', 'slug', 'descricao', 'imagem')
        }),
        ('Data e Local', {
            'fields': ('data_inicio', 'data_fim', 'local', 'link_inscricao')
        }),
        ('Configurações', {
            'fields': ('ativo', 'data_criacao')
        }),
    )

    def imagem_thumbnail(self, obj):
        if obj.imagem:
            return format_html(
                '<img src="{}" width="90" height="55" style="object-fit:cover;border-radius:6px;" />',
                obj.imagem.url,
            )
        return '-'
    imagem_thumbnail.short_description = 'Imagem'


class EspecialidadeAdmin(admin.ModelAdmin):
    list_display = ['imagem_thumbnail', 'titulo', 'slug', 'ordem', 'ativo', 'data_criacao']
    list_display_links = ['titulo']
    list_filter = ['ativo', 'data_criacao']
    search_fields = ['titulo', 'slug']
    list_editable = ['ordem', 'ativo']
    prepopulated_fields = {'slug': ('titulo',)}
    readonly_fields = ['data_criacao']
    fieldsets = (
        ('Informações', {
            'fields': ('titulo', 'slug', 'descricao', 'imagem')
        }),
        ('Configurações', {
            'fields': ('ordem', 'ativo', 'data_criacao')
        }),
    )

    def imagem_thumbnail(self, obj):
        if obj.imagem:
            return format_html(
                '<img src="{}" width="90" height="55" style="object-fit:cover;border-radius:6px;" />',
                obj.imagem.url,
            )
        return '-'
    imagem_thumbnail.short_description = 'Imagem'


class NewsletterInscricaoAdmin(admin.ModelAdmin):
    list_display = ['email', 'nome', 'origem', 'ativo', 'data_criacao']
    list_filter = ['origem', 'ativo', 'data_criacao']
    search_fields = ['email', 'nome']
    readonly_fields = ['data_criacao']


class CarrosselAdmin(admin.ModelAdmin):
    list_display = ['imagem_thumbnail', 'titulo', 'ordem', 'ativo', 'data_criacao']
    list_display_links = ['titulo']
    list_filter = ['ativo', 'data_criacao']
    search_fields = ['titulo', 'subtitulo']
    list_editable = ['ordem', 'ativo']
    readonly_fields = ['data_criacao']
    fieldsets = (
        ('Imagem', {
            'fields': ('imagem', 'foto', 'titulo', 'subtitulo'),
        }),
        ('Botão 1', {
            'fields': ('botao1_texto', 'botao1_tipo', 'botao1_link'),
            'description': 'Preencha "Texto" e "Tipo". Para o tipo "página interna", o campo Link deve ser: sobre, solucoes, eventos, especialidades, blog ou home. Para "link externo", cole a URL completa (ex.: https://calendly.com/...).',
        }),
        ('Botão 2', {
            'fields': ('botao2_texto', 'botao2_tipo', 'botao2_link'),
            'description': 'Mesmas regras do Botão 1.',
        }),
        ('Configurações', {
            'fields': ('ordem', 'ativo', 'data_criacao'),
        }),
    )

    def imagem_thumbnail(self, obj):
        if obj.imagem:
            return format_html(
                '<img src="{}" width="90" height="55" style="object-fit:cover;border-radius:6px;" />',
                obj.imagem.url,
            )
        return '-'
    imagem_thumbnail.short_description = 'Imagem'


class SobreNosFotoAdmin(admin.ModelAdmin):
    list_display = ['imagem_thumbnail', 'titulo', 'ordem', 'ativo', 'data_criacao']
    list_display_links = ['titulo']
    list_filter = ['ativo', 'data_criacao']
    search_fields = ['titulo']
    list_editable = ['ordem', 'ativo']
    readonly_fields = ['data_criacao']
    fieldsets = (
        ('Imagem', {
            'fields': ('imagem', 'titulo'),
            'description': 'Foto exibida no carrossel 3D da seção Sobre Nós. Recomendado: proporção retrato.',
        }),
        ('Configurações', {
            'fields': ('ordem', 'ativo', 'data_criacao'),
        }),
    )

    def imagem_thumbnail(self, obj):
        if obj.imagem:
            return format_html(
                '<img src="{}" width="90" height="55" style="object-fit:cover;border-radius:6px;" />',
                obj.imagem.url,
            )
        return '-'
    imagem_thumbnail.short_description = 'Imagem'


# Registrar os models no admin_site customizado
admin_site.register(Usuario, UsuarioAdmin)
admin_site.register(PostBlog, PostBlogAdmin)
admin_site.register(Ebook, EbookAdmin)
admin_site.register(Evento, EventoAdmin)
admin_site.register(PageView, PageViewAdmin)
admin_site.register(ContactLead, ContactLeadAdmin)
admin_site.register(JobApplication, JobApplicationAdmin)
admin_site.register(Especialidade, EspecialidadeAdmin)
admin_site.register(NewsletterInscricao, NewsletterInscricaoAdmin)
admin_site.register(Carrossel, CarrosselAdmin)
admin_site.register(SobreNosFoto, SobreNosFotoAdmin)


class ClienteAdmin(admin.ModelAdmin):
    list_display = ['nome', 'email', 'celular', 'cpf', 'cnpj', 'data_criacao', 'ultimo_acesso']
    search_fields = ['nome', 'email', 'celular', 'cpf', 'cnpj']
    readonly_fields = ['nome', 'email', 'celular', 'cpf', 'cnpj', 'auth_token', 'data_criacao', 'ultimo_acesso']
    list_filter = ['data_criacao']


admin_site.register(Cliente, ClienteAdmin)
