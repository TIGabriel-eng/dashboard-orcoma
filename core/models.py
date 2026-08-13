from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone


class Usuario(AbstractUser):
    """Modelo de usuário customizado para administradores"""
    CARGO_CHOICES = (
        ('admin', 'Admin'),
        ('social_media', 'Social Media'),
        ('rh', 'RH'),
        ('comercial', 'Comercial'),
        # Valores legados — mantidos apenas para não quebrar exibição de
        # usuários antigos. Não recebem permissões automáticas.
        ('editor', 'Editor (legado)'),
        ('moderador', 'Moderador (legado)'),
    )
    
    cargo = models.CharField(max_length=20, choices=CARGO_CHOICES, default='moderador')
    telefone = models.CharField(max_length=15, blank=True, null=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    
    class Meta:
        verbose_name = 'Usuário'
        verbose_name_plural = 'Usuários'
        ordering = ['-date_joined']
    
    def __str__(self):
        return f"{self.get_full_name()} ({self.get_cargo_display()})"


class PostBlog(models.Model):
    """Modelo para posts do blog"""
    STATUS_CHOICES = (
        ('rascunho', 'Rascunho'),
        ('publicado', 'Publicado'),
    )
    
    titulo = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    conteudo = models.TextField(help_text='Conteúdo completo do post (exibido na página do post).')
    resumo = models.TextField(max_length=300, blank=True, help_text='Texto curto exibido no card do blog.')
    imagem_destaque = models.ImageField(upload_to='blog/', blank=True, null=True, help_text='Imagem exibida no card do blog.')
    autor = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='posts')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='rascunho')
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_publicacao = models.DateTimeField(blank=True, null=True)
    visualizacoes = models.IntegerField(default=0)
    
    class Meta:
        verbose_name = 'Post do Blog'
        verbose_name_plural = 'Posts do Blog'
        ordering = ['-data_criacao']
    
    def __str__(self):
        return self.titulo
    
    def save(self, *args, **kwargs):
        if self.status == 'publicado' and not self.data_publicacao:
            self.data_publicacao = timezone.now()
        super().save(*args, **kwargs)


class PostVisualizacao(models.Model):
    """Registra a primeira visualização de um artigo por IP (evita contar duplicado)."""
    post = models.ForeignKey(PostBlog, on_delete=models.CASCADE, related_name='visualizacoes_por_ip')
    ip_address = models.GenericIPAddressField()
    primeira_visita = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Visualização de Post'
        verbose_name_plural = 'Visualizações de Post'
        unique_together = [('post', 'ip_address')]
        ordering = ['-primeira_visita']

    def __str__(self):
        return f"{self.post.titulo} - {self.ip_address}"


class Ebook(models.Model):
    """Modelo para ebooks"""
    titulo = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    descricao = models.TextField()
    arquivo = models.FileField(upload_to='ebooks/')
    imagem_capa = models.ImageField(upload_to='ebooks/capas/', blank=True, null=True)
    downloads = models.IntegerField(default=0)
    data_criacao = models.DateTimeField(auto_now_add=True)
    ativo = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = 'Ebook'
        verbose_name_plural = 'Ebooks'
        ordering = ['-data_criacao']
    
    def __str__(self):
        return self.titulo


class Evento(models.Model):
    """Modelo para eventos"""
    titulo = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    descricao = models.TextField()
    data_inicio = models.DateTimeField()
    data_fim = models.DateTimeField()
    local = models.CharField(max_length=300)
    imagem = models.ImageField(upload_to='eventos/', blank=True, null=True)
    link_inscricao = models.URLField(blank=True, null=True)
    ativo = models.BooleanField(default=True)
    data_criacao = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Evento'
        verbose_name_plural = 'Eventos'
        ordering = ['data_inicio']
    
    def __str__(self):
        return self.titulo
    
    @property
    def is_upcoming(self):
        return self.data_inicio > timezone.now()


class PageView(models.Model):
    """Registro de visita/acesso ao site"""
    path = models.CharField(max_length=500, blank=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Acesso'
        verbose_name_plural = 'Acessos'
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.path} - {self.timestamp.strftime('%d/%m/%Y %H:%M')}"


class ContactLead(models.Model):
    """Lead gerado pelas formas de contato do site (formulários e cliques em WhatsApp)"""
    ORIGEM_CHOICES = (
        ('site', 'Site (legado)'),
        ('home_form', 'Formulário da Home'),
        ('pagina_contato', 'Página de Contato'),
        ('blog_lead', 'Lead do Blog'),
        ('whatsapp_modal', 'Modal de WhatsApp'),
        ('whatsapp_direto', 'WhatsApp direto (clique)'),
        ('solucoes', 'Soluções (logado)'),
        ('academy_business', 'Academy Business'),
    )

    INTERESSE_CHOICES = (
        ('geral', 'Só entrar em contato'),
        ('abrir_empresa', 'Abertura de Empresa'),
        ('migracao_contabilidade', 'Migração de Contabilidade'),
        ('migracao_mei_me', 'Migração de MEI para ME'),
        ('declaracao_irpf', 'Declaração IRPF'),
    )

    nome = models.CharField(max_length=200, blank=True)
    celular = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    cpf = models.CharField(max_length=14, blank=True, help_text='CPF informado pelo visitante (opcional)')
    cnpj = models.CharField(max_length=20, blank=True)
    mensagem = models.TextField(blank=True, help_text='Mensagem opcional enviada pelo visitante')
    origem = models.CharField(max_length=50, choices=ORIGEM_CHOICES, default='site', help_text='De onde veio o contato (formulário, página, clique em WhatsApp, etc.)')
    interesse = models.CharField(max_length=50, choices=INTERESSE_CHOICES, default='geral', help_text='Interesse principal do visitante')
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Lead de Contato'
        verbose_name_plural = 'Leads de Contato'
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.nome or 'Clique WhatsApp'} - {self.email or self.origem}"


class JobApplication(models.Model):
    """Candidatura enviada pelo formulário Trabalhe Conosco"""
    nome = models.CharField(max_length=200)
    email = models.EmailField()
    telefone = models.CharField(max_length=20, blank=True)
    mensagem = models.TextField(blank=True)
    curriculo = models.FileField(upload_to='curriculos/', blank=True, null=True)
    preview = models.ImageField(upload_to='curriculos/previews/', blank=True, null=True, help_text='Imagem da primeira página do currículo (gerada automaticamente para PDFs).')
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Candidatura'
        verbose_name_plural = 'Trabalhe Conosco'
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.nome} - {self.email}"


class Especialidade(models.Model):
    """Especialidades da Orcoma exibidas na seção 'Somos especialistas quando o assunto é:'"""
    titulo = models.CharField(max_length=200, help_text='Título da especialidade (ex: Iniciativa Pública)')
    slug = models.SlugField(unique=True, help_text='Identificador usado na URL da página da especialidade (ex: iniciativa-publica)')
    descricao = models.TextField(blank=True, help_text='Descrição da especialidade, exibida na página de detalhe no site')
    imagem = models.ImageField(upload_to='especialidades/', help_text='Imagem de fundo da especialidade')
    ordem = models.IntegerField(default=0, help_text='Ordem de exibição (menor = primeiro)')
    ativo = models.BooleanField(default=True, help_text='Exibir esta especialidade no site')
    data_criacao = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Especialidade'
        verbose_name_plural = 'Especialidades'
        ordering = ['ordem', 'titulo']

    def __str__(self):
        return self.titulo


class NewsletterInscricao(models.Model):
    """Inscrição na newsletter: e-mails de clientes que querem ficar por dentro das novidades"""
    ORIGEM_CHOICES = (
        ('eventos', 'Eventos'),
        ('contato', 'Contato'),
        ('footer', 'Footer'),
        ('blog', 'Blog'),
    )

    email = models.EmailField(unique=True, help_text='E-mail do cliente')
    nome = models.CharField(max_length=200, blank=True, help_text='Nome do cliente (opcional)')
    celular = models.CharField(max_length=30, blank=True, help_text='Celular do cliente (opcional)')
    origem = models.CharField(max_length=20, choices=ORIGEM_CHOICES, default='footer')
    ativo = models.BooleanField(default=True, help_text='Assinatura ativa (não cancelada)')
    data_criacao = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Inscrição de Newsletter'
        verbose_name_plural = 'Inscrições de Newsletter'
        ordering = ['-data_criacao']

    def __str__(self):
        return self.email


class Carrossel(models.Model):
    """Imagens do carrossel do hero da home, gerenciadas pelo Django Admin."""
    BOTAO_CHOICES = (
        ('nenhum', 'Nenhum (não exibir botão)'),
        ('whatsapp', 'Abrir modal de WhatsApp'),
        ('contato', 'Ir para a página de Contato'),
        ('pagina', 'Ir para uma página interna'),
        ('externo', 'Abrir link externo (nova aba)'),
    )

    titulo = models.CharField(max_length=200, blank=True, help_text='Título exibido sobre a imagem (opcional)')
    subtitulo = models.CharField(max_length=300, blank=True, help_text='Texto de apoio exibido abaixo do título (opcional)')
    imagem = models.ImageField(upload_to='carrossel/', blank=True, null=True, help_text='Imagem de fundo do carrossel (recomendado: 1950x700). Opcional se houver foto de pessoa.')
    foto = models.ImageField(upload_to='carrossel/pessoas/', blank=True, null=True, help_text='Foto de pessoa exibida ao lado do texto, sem imagem de fundo (opcional)')
    botao1_texto = models.CharField(max_length=60, blank=True, help_text='Texto do botão 1 (ex.: Agende sua Reunião)')
    botao1_tipo = models.CharField(max_length=20, choices=BOTAO_CHOICES, default='nenhum', help_text='O que o botão 1 faz ao ser clicado')
    botao1_link = models.CharField(max_length=500, blank=True, help_text='Para "página interna": use sobre, solucoes, eventos, especialidades, blog ou home. Para "link externo": cole a URL completa (ex.: https://calendly.com/...)')
    botao2_texto = models.CharField(max_length=60, blank=True, help_text='Texto do botão 2 (ex.: Fale conosco)')
    botao2_tipo = models.CharField(max_length=20, choices=BOTAO_CHOICES, default='nenhum', help_text='O que o botão 2 faz ao ser clicado')
    botao2_link = models.CharField(max_length=500, blank=True, help_text='Para "página interna": use sobre, solucoes, eventos, especialidades, blog ou home. Para "link externo": cole a URL completa')
    ordem = models.IntegerField(default=0, help_text='Ordem de exibição (menor = primeiro)')
    ativo = models.BooleanField(default=True, help_text='Exibir esta imagem no carrossel do site')
    data_criacao = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Imagem do Carrossel'
        verbose_name_plural = 'Carrossel'
        ordering = ['ordem', 'data_criacao']

    def __str__(self):
        return self.titulo or f'Slide {self.pk}'


class SobreNosFoto(models.Model):
    """Fotos do carrossel 3D da seção 'Sobre Nós', gerenciadas pelo Django Admin."""
    titulo = models.CharField(max_length=200, blank=True, help_text='Legenda da foto, exibida como texto alternativo (opcional)')
    imagem = models.ImageField(upload_to='sobrenos/', help_text='Imagem exibida no carrossel 3D da seção Sobre Nós (recomendado: proporção retrato)')
    ordem = models.IntegerField(default=0, help_text='Ordem de exibição (menor = primeiro)')
    ativo = models.BooleanField(default=True, help_text='Exibir esta foto na seção Sobre Nós do site')
    data_criacao = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Foto Sobre Nós'
        verbose_name_plural = 'Sobre Nós Fotos'
        ordering = ['ordem', 'data_criacao']

    def __str__(self):
        return self.titulo or f'Foto {self.pk}'


class Cliente(models.Model):
    """Cliente cadastrado/logado pelo modal de acesso aos serviços do site."""
    nome = models.CharField(max_length=200)
    email = models.EmailField(unique=True)
    celular = models.CharField(max_length=20)
    cpf = models.CharField(max_length=14, blank=True, null=True, unique=True, help_text='CPF do cliente (opcional)')
    cnpj = models.CharField(max_length=20, blank=True, help_text='CNPJ do cliente (opcional)')
    auth_token = models.CharField(max_length=64, blank=True, unique=True, help_text='Token de sessão gerado no login')
    data_criacao = models.DateTimeField(auto_now_add=True)
    ultimo_acesso = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'
        ordering = ['-data_criacao']

    def __str__(self):
        return f"{self.nome} - {self.email}"


class IPSuspeito(models.Model):
    """IP marcado como suspeito (automaticamente ou pelo administrador).

    A penalidade é apenas de visibilidade: o sistema nunca bloqueia tráfego
    automaticamente. O administrador decide o que fazer com cada IP.
    """
    NIVEL_CHOICES = (
        (1, 'Baixo'),
        (2, 'Médio'),
        (3, 'Alto'),
    )

    ip_address = models.GenericIPAddressField(unique=True, db_index=True)
    nivel = models.PositiveSmallIntegerField(choices=NIVEL_CHOICES, default=2, help_text='Gravidade estimada do comportamento')
    motivo = models.TextField(blank=True, help_text='Por que este IP foi marcado (preenchido automaticamente; pode ser editado)')
    resolvido = models.BooleanField(default=False, db_index=True, help_text='Marque quando o acesso for investigado e deixar de ser uma ameaça')
    data_criacao = models.DateTimeField(auto_now_add=True)
    ultima_visto = models.DateTimeField(auto_now=True, help_text='Última vez que este IP teve atividade flagrada')

    class Meta:
        verbose_name = 'IP Suspeito'
        verbose_name_plural = 'IPs Suspeitos'
        ordering = ['-resolvido', '-ultima_visto']

    def __str__(self):
        status = 'resolvido' if self.resolvido else 'em análise'
        return f'{self.ip_address} ({status})'


class SecurityEvent(models.Model):
    """Evento de segurança detectado automaticamente no site.

    Cada evento guarda o que aconteceu (tipo), de onde veio (IP), qual
    caminho/agente estava envolvido e quando. Serve de trilha de auditoria
    para o administrador investigar acessos suspeitos.
    """
    TIPO_CHOICES = (
        ('request_rate', 'Muitas requisições'),
        ('path_invasivo', 'Path de ataque/scanner'),
        ('user_agent_suspeito', 'User-Agent suspeito'),
        ('injecao', 'Tentativa de injeção'),
        ('honeypot', 'Bot detectado (honeypot)'),
        ('falha_recaptcha', 'Falha no reCAPTCHA'),
        ('rate_limit', 'Limite de contato excedido'),
        ('upload_invalido', 'Upload inválido'),
        ('login_admin', 'Acesso ao admin (sem permissão)'),
        ('outro', 'Outro'),
    )

    tipo = models.CharField(max_length=30, choices=TIPO_CHOICES, db_index=True)
    ip_address = models.GenericIPAddressField(db_index=True)
    path = models.CharField(max_length=500, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)
    detalhes = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Evento de Segurança'
        verbose_name_plural = 'Eventos de Segurança'
        ordering = ['-timestamp']

    def __str__(self):
        return f'{self.get_tipo_display()} - {self.ip_address}'

    def get_tipo_label(self):
        return dict(self.TIPO_CHOICES).get(self.tipo, self.tipo)
