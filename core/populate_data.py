#!/usr/bin/env python
import os
import sys
import django
from datetime import datetime, timedelta
from django.utils import timezone

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'orcoma_admin.settings')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

from core.models import Usuario, PostBlog, Ebook, Evento, Especialidade

def create_sample_data():
    print("Criando dados de exemplo...")
    
    # Criar usuÃ¡rios adicionais
    print("\n1. Criando usuÃ¡rios...")
    usuarios_data = [
        {
            'username': 'joao.silva',
            'email': 'joao.silva@orcoma.com',
            'password': 'user123',
            'first_name': 'JoÃ£o',
            'last_name': 'Silva',
            'cargo': 'moderador',
            'is_staff': True,
        },
        {
            'username': 'maria.santos',
            'email': 'maria.santos@orcoma.com',
            'password': 'user123',
            'first_name': 'Maria',
            'last_name': 'Santos',
            'cargo': 'editor',
            'is_staff': True,
        },
        {
            'username': 'ricardo.oliveira',
            'email': 'ricardo.oliveira@orcoma.com',
            'password': 'user123',
            'first_name': 'Ricardo',
            'last_name': 'Oliveira',
            'cargo': 'admin',
            'is_staff': True,
        },
    ]
    
    usuarios = []
    for user_data in usuarios_data:
        usuario, created = Usuario.objects.get_or_create(
            username=user_data['username'],
            defaults={
                'email': user_data['email'],
                'first_name': user_data['first_name'],
                'last_name': user_data['last_name'],
                'cargo': user_data['cargo'],
                'is_staff': user_data['is_staff'],
                'is_active': True,
            }
        )
        if created:
            usuario.set_password(user_data['password'])
            usuario.save()
            print(f"  âœ“ UsuÃ¡rio criado: {usuario.get_full_name()}")
        else:
            print(f"  - UsuÃ¡rio jÃ¡ existe: {usuario.get_full_name()}")
        usuarios.append(usuario)
    
    # Criar posts do blog
    print("\n2. Criando posts do blog...")
    posts_data = [
        {
            'titulo': 'Novas regras para prestaÃ§Ã£o de contas',
            'slug': 'novas-regras-prestacao-contas',
            'conteudo': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.',
            'resumo': 'Confira as novas diretrizes para prestaÃ§Ã£o de contas no Grupo Orcoma.',
            'autor': usuarios[1],  # Maria Santos
            'status': 'publicado',
            'data_publicacao': timezone.now() - timedelta(days=2),
        },
        {
            'titulo': 'A IA na auditoria governamental',
            'slug': 'ia-auditoria-governamental',
            'conteudo': 'Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.',
            'resumo': 'Como a inteligÃªncia artificial estÃ¡ transformando a auditoria governamental.',
            'autor': usuarios[0],  # JoÃ£o Silva
            'status': 'publicado',
            'data_publicacao': timezone.now() - timedelta(days=5),
        },
        {
            'titulo': 'Dicas para melhorar a gestÃ£o pÃºblica',
            'slug': 'dicas-melhorar-gestao-publica',
            'conteudo': 'Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur.',
            'resumo': 'Aprenda dicas prÃ¡ticas para melhorar a gestÃ£o pÃºblica municipal.',
            'autor': usuarios[2],  # Ricardo Oliveira
            'status': 'rascunho',
            'data_publicacao': None,
        },
        {
            'titulo': 'Trocar de contador: vantagens para o seu negÃ³cio',
            'slug': 'trocar-de-contador-vantagens',
            'conteudo': (
                'Trocar de contador pode parecer um passo delicado, mas muitas vezes Ã© exatamente o que a sua empresa precisa para '
                'alcanÃ§ar um novo patamar de organizaÃ§Ã£o e crescimento.\n\n'
                'Muitos empresÃ¡rios permanecem com o mesmo contador por comodidade ou medo de burocracia, porÃ©m uma assessoria '
                'contÃ¡bil desatualizada pode custar caro â€” tanto em impostos pagos a mais quanto em oportunidades perdidas.\n\n'
                'Quando vale a pena trocar de contador?\n\n'
                '1. Falta de proatividade: o contador que apenas cumpre obrigaÃ§Ãµes e nunca traz insights estratÃ©gicos.\n'
                '2. Erros recorrentes: inconsistÃªncias em guias, declaraÃ§Ãµes ou prazos perdidos.\n'
                '3. ComunicaÃ§Ã£o deficiente: demora para responder ou ausÃªncia de explicaÃ§Ãµes claras.\n'
                '4. Economia tributÃ¡ria: a empresa pode estar pagando impostos acima do necessÃ¡rio.\n\n'
                'Ao escolher um novo contador, avalie a experiÃªncia da equipe, a tecnologia utilizada, a clareza na comunicaÃ§Ã£o e, '
                'principalmente, o alinhamento com os objetivos do seu negÃ³cio.\n\n'
                'Na Orcoma, acreditamos que a contabilidade deve ser uma parceira estratÃ©gica do empreendedor, oferecendo nÃ£o '
                'apenas conformidade fiscal, mas tambÃ©m inteligÃªncia para a tomada de decisÃµes.'
            ),
            'resumo': 'Trocar de contador pode trazer benefÃ­cios exclusivos para o seu negÃ³cio. Veja quando faz sentido dar o passo e o que observar antes de decidir.',
            'autor': usuarios[0],  # JoÃ£o Silva
            'status': 'publicado',
            'data_publicacao': timezone.now() - timedelta(days=30),
        },
        {
            'titulo': 'EmpresÃ¡rio, saiba como lidar com clientes que reclamam dos preÃ§os',
            'slug': 'lidar-com-clientes-que-reclamam-precos',
            'conteudo': (
                'Contornar objeÃ§Ãµes de preÃ§o Ã© um dos grandes desafios de qualquer empresÃ¡rio. O cliente que reclama do valor '
                'nem sempre quer pagar menos â€” muitas vezes ele precisa enxergar mais valor no que estÃ¡ comprando.\n\n'
                'EstratÃ©gias prÃ¡ticas para lidar com objeÃ§Ãµes de preÃ§o:\n\n'
                '1. Escute antes de responder: entenda a real objeÃ§Ã£o do cliente antes de tentar justificar o preÃ§o.\n'
                '2. Reforce o valor: destaque os benefÃ­cios, a qualidade e o suporte que acompanham o seu produto ou serviÃ§o.\n'
                '3. Compare com o mercado: mostre como o seu preÃ§o Ã© justo diante do que a concorrÃªncia oferece.\n'
                '4. OfereÃ§a alternativas: pacotes, prazos ou condiÃ§Ãµes de pagamento podem facilitar a decisÃ£o.\n\n'
                'Lembre-se: desvalorizar o seu produto para fechar venda Ã© um tiro no pÃ©. Quando o cliente percebe que o preÃ§o '
                'reflete o valor entregue, a negociaÃ§Ã£o flui naturalmente.'
            ),
            'resumo': 'Contornar objeÃ§Ãµes de preÃ§o Ã© um passo importante da negociaÃ§Ã£o. Entenda estratÃ©gias prÃ¡ticas para manter a venda sem desvalorizar o produto.',
            'autor': usuarios[2],  # Ricardo Oliveira
            'status': 'publicado',
            'data_publicacao': timezone.now() - timedelta(days=40),
        },
        {
            'titulo': 'Vendas em queda: fique por dentro dos Ã­ndices e proteja sua empresa',
            'slug': 'vendas-em-queda-indices',
            'conteudo': (
                'Quando as vendas comeÃ§am a cair, muitos empresÃ¡rios entram em pÃ¢nico e tomam decisÃµes precipitadas. PorÃ©m, '
                'entender primeiro os Ã­ndices e as causas da queda Ã© essencial para agir com estratÃ©gia.\n\n'
                'No levantamento, a retraÃ§Ã£o foi disseminada, tendo como exceÃ§Ã£o apenas alguns setores. Isso significa que nÃ£o '
                'se trata de um problema isolado do seu negÃ³cio, mas de um cenÃ¡rio mais amplo.\n\n'
                'Como se antecipar aos cenÃ¡rios de queda:\n\n'
                '1. Acompanhe indicadores financeiros mensalmente: receita, margem, ticket mÃ©dio e inadimplÃªncia.\n'
                '2. Reduza custos com inteligÃªncia: elimine desperdÃ­cios sem cortar o que gera valor.\n'
                '3. Diversifique canais de venda: presencial, digital, marketplace e parcerias.\n'
                '4. Reforce o relacionamento com clientes existentes: Ã© mais barato e mais seguro do que prospectar.\n\n'
                'A queda de vendas nÃ£o precisa ser o fim â€” pode ser um alerta para a empresa se reorganizar e sair mais forte.'
            ),
            'resumo': 'No levantamento, a retraÃ§Ã£o foi disseminada, tendo como exceÃ§Ã£o apenas alguns setores. Veja como se antecipar aos cenÃ¡rios de queda.',
            'autor': usuarios[1],  # Maria Santos
            'status': 'publicado',
            'data_publicacao': timezone.now() - timedelta(days=55),
        },
        {
            'titulo': 'Reforma tributÃ¡ria: o que jÃ¡ estÃ¡ valendo em 2026',
            'slug': 'reforma-tributaria-2026',
            'conteudo': (
                'A reforma tributÃ¡ria Ã© um dos temas mais importantes para as empresas brasileiras nos prÃ³ximos anos. '
                'Em 2026, alguns pontos jÃ¡ comeÃ§am a valer e Ã© fundamental estar preparado.\n\n'
                'O que jÃ¡ estÃ¡ valendo em 2026:\n\n'
                '1. Novas regras de transiÃ§Ã£o para alguns tributos federais.\n'
                '2. ObrigaÃ§Ãµes acessÃ³rias atualizadas para se adequar ao novo sistema.\n'
                '3. MudanÃ§as na forma de creditamento e apuraÃ§Ã£o em alguns setores.\n\n'
                'O que ainda estÃ¡ em fase de transiÃ§Ã£o:\n\n'
                'â€¢ A unificaÃ§Ã£o completa dos tributos sobre consumo (IBS e CBS).\n'
                'â€¢ A implementaÃ§Ã£o do split payment e os novos mecanismos de apuraÃ§Ã£o.\n'
                'â€¢ As alÃ­quotas definitivas e os regimes especÃ­ficos por setor.\n\n'
                'A melhor estratÃ©gia Ã© contar com uma assessoria contÃ¡bil especializada que acompanhe cada etapa da transiÃ§Ã£o '
                'e mantenha a sua empresa em dia com as novas obrigaÃ§Ãµes.'
            ),
            'resumo': 'Um guia direto sobre os pontos da reforma que jÃ¡ impactam a rotina fiscal das empresas e o que ainda estÃ¡ em fase de transiÃ§Ã£o.',
            'autor': usuarios[0],  # JoÃ£o Silva
            'status': 'publicado',
            'data_publicacao': timezone.now() - timedelta(days=3),
        },
        {
            'titulo': 'PrestaÃ§Ã£o de contas: como manter a transparÃªncia na gestÃ£o pÃºblica',
            'slug': 'prestacao-contas-transparencia-gestao-publica',
            'conteudo': (
                'A prestaÃ§Ã£o de contas Ã© um dos pilares da gestÃ£o pÃºblica responsÃ¡vel. Quando feita com transparÃªncia e '
                'organizaÃ§Ã£o, gera confianÃ§a da populaÃ§Ã£o e evita problemas com Ã³rgÃ£os de controle.\n\n'
                'Boas prÃ¡ticas para manter a transparÃªncia:\n\n'
                '1. Controle interno robusto: registre todas as operaÃ§Ãµes de forma clara e documentada.\n'
                '2. PublicaÃ§Ã£o regular: mantenha os portais de transparÃªncia atualizados.\n'
                '3. Conciliar sempre: verifique os extratos bancÃ¡rios com os registros contÃ¡beis.\n'
                '4. CapacitaÃ§Ã£o da equipe: servidores bem treinados cometem menos erros.\n\n'
                'Ao adotar essas prÃ¡ticas, o gestor pÃºblico reduz o risco de apontamentos em auditoria, fortalece a imagem da '
                'gestÃ£o e garante que os recursos sejam utilizados com responsabilidade.'
            ),
            'resumo': 'Boas prÃ¡ticas de controle interno ajudam gestores pÃºblicos a usar os recursos com responsabilidade e evitar apontamentos em auditoria.',
            'autor': usuarios[2],  # Ricardo Oliveira
            'status': 'publicado',
            'data_publicacao': timezone.now() - timedelta(days=8),
        },
        {
            'titulo': 'Planejamento financeiro anual: por onde comeÃ§ar',
            'slug': 'planejamento-financeiro-anual',
            'conteudo': (
                'Um bom planejamento financeiro anual Ã© a diferenÃ§a entre empresas que crescem com previsibilidade e aquelas '
                'que vivem apagando incÃªndios.\n\n'
                'Por onde comeÃ§ar:\n\n'
                '1. DiagnÃ³stico: analise o cenÃ¡rio atual â€” receitas, despesas, dÃ­vidas e fluxo de caixa.\n'
                '2. Metas claras: defina objetivos realistas de faturamento, lucro e reduÃ§Ã£o de custos.\n'
                '3. OrÃ§amento: projete as receitas e despesas mÃªs a mÃªs.\n'
                '4. Reserva de emergÃªncia: destine um percentual do faturamento para imprevistos.\n'
                '5. RevisÃ£o periÃ³dica: acompanhe os resultados mensalmente e ajuste a rota.\n\n'
                'Com disciplina e as ferramentas certas, qualquer empresa â€” de qualquer porte â€” pode estruturar um planejamento '
                'que traga seguranÃ§a e crescimento.'
            ),
            'resumo': 'Um roteiro simples para estruturar o planejamento financeiro da sua empresa e chegar ao prÃ³ximo ano com metas claras.',
            'autor': usuarios[1],  # Maria Santos
            'status': 'publicado',
            'data_publicacao': timezone.now() - timedelta(days=15),
        },
    ]
    
    for post_data in posts_data:
        post, created = PostBlog.objects.update_or_create(
            slug=post_data['slug'],
            defaults=post_data
        )
        if created:
            print(f"  âœ“ Post criado: {post.titulo}")
        else:
            print(f"  âœ“ Post atualizado: {post.titulo}")
    
    # Criar ebooks
    print("\n3. Criando ebooks...")
    ebooks_data = [
        {
            'titulo': 'Guia do Gestor',
            'slug': 'guia-do-gestor',
            'descricao': 'Um guia completo para gestores pÃºblicos',
            'ativo': True,
        },
        {
            'titulo': 'Compliance 2024',
            'slug': 'compliance-2024',
            'descricao': 'Manual de compliance para organizaÃ§Ãµes pÃºblicas',
            'ativo': True,
        },
        {
            'titulo': 'Auditoria Moderna',
            'slug': 'auditoria-moderna',
            'descricao': 'TÃ©cnicas modernas de auditoria governamental',
            'ativo': True,
        },
    ]
    
    for ebook_data in ebooks_data:
        ebook, created = Ebook.objects.get_or_create(
            slug=ebook_data['slug'],
            defaults=ebook_data
        )
        if created:
            print(f"  âœ“ Ebook criado: {ebook.titulo}")
        else:
            print(f"  - Ebook jÃ¡ existe: {ebook.titulo}")
    
    # Criar eventos
    print("\n4. Criando eventos...")
    eventos_data = [
        {
            'titulo': 'Workshop de GestÃ£o PÃºblica',
            'slug': 'workshop-gestao-publica',
            'descricao': 'Workshop intensivo sobre gestÃ£o pÃºblica moderna',
            'data_inicio': timezone.now() + timedelta(days=15),
            'data_fim': timezone.now() + timedelta(days=15, hours=8),
            'local': 'Centro de ConvenÃ§Ãµes Orcoma',
            'link_inscricao': 'https://orcoma.com/eventos/workshop',
            'ativo': True,
        },
        {
            'titulo': 'SeminÃ¡rio de Compliance',
            'slug': 'seminario-compliance',
            'descricao': 'SeminÃ¡rio anual sobre compliance e Ã©tica',
            'data_inicio': timezone.now() + timedelta(days=30),
            'data_fim': timezone.now() + timedelta(days=30, hours=6),
            'local': 'AuditÃ³rio Principal',
            'link_inscricao': 'https://orcoma.com/eventos/compliance',
            'ativo': True,
        },
        {
            'titulo': 'ConferÃªncia de Auditoria',
            'slug': 'conferencia-auditoria',
            'descricao': 'ConferÃªncia sobre novas tÃ©cnicas de auditoria',
            'data_inicio': timezone.now() + timedelta(days=45),
            'data_fim': timezone.now() + timedelta(days=46),
            'local': 'Online - Zoom',
            'link_inscricao': 'https://orcoma.com/eventos/auditoria',
            'ativo': True,
        },
    ]
    
    for evento_data in eventos_data:
        evento, created = Evento.objects.get_or_create(
            slug=evento_data['slug'],
            defaults=evento_data
        )
        if created:
            print(f"  âœ“ Evento criado: {evento.titulo}")
        else:
            print(f"  - Evento jÃ¡ existe: {evento.titulo}")
    
    # Criar especialidades
    print("\n5. Criando especialidades...")
    especialidades_data = [
        {
            'titulo': 'Iniciativa PÃºblica',
            'slug': 'iniciativa-publica',
            'descricao': 'Assessoria especializada para Ã³rgÃ£os pÃºblicos, garantindo conformidade fiscal, transparÃªncia e a correta aplicaÃ§Ã£o dos recursos pÃºblicos.',
            'imagem': 'especialidades/iniciativa-publica.jpg',
            'ordem': 1,
            'ativo': True,
        },
        {
            'titulo': 'ComÃ©rcio Varejista e Atacadista',
            'slug': 'comercio-varejista-e-atacadista',
            'descricao': 'Contabilidade estratÃ©gica para lojas e distribuidoras, com foco em reduÃ§Ã£o de impostos e gestÃ£o financeira saudÃ¡vel.',
            'imagem': 'especialidades/comercio.jpg',
            'ordem': 2,
            'ativo': True,
        },
        {
            'titulo': 'MÃ©dicos, ClÃ­nicas MÃ©dicas e Profissionais da Ãrea da SaÃºde',
            'slug': 'medicos-clinicas-medicas-e-profissionais-da-area-da-saude',
            'descricao': 'Planejamento tributÃ¡rio e contabilidade voltados para mÃ©dicos, clÃ­nicas e profissionais da saÃºde.',
            'imagem': 'especialidades/saude.jpg',
            'ordem': 3,
            'ativo': True,
        },
        {
            'titulo': 'Hospitais',
            'slug': 'hospitais',
            'descricao': 'GestÃ£o contÃ¡bil completa para hospitais, unindo conformidade, controles internos e eficiÃªncia operacional.',
            'imagem': 'especialidades/hospitais.jpg',
            'ordem': 4,
            'ativo': True,
        },
        {
            'titulo': 'Terceiro Setor',
            'slug': 'terceiro-setor',
            'descricao': 'Assessoria contÃ¡bil para ONGs, associaÃ§Ãµes e fundaÃ§Ãµes, com foco em prestaÃ§Ã£o de contas e sustentabilidade.',
            'imagem': 'especialidades/terceiro-setor.jpg',
            'ordem': 5,
            'ativo': True,
        },
        {
            'titulo': 'ConstruÃ§Ã£o Civil',
            'slug': 'construcao-civil',
            'descricao': 'EspecializaÃ§Ã£o em contabilidade para construtoras e incorporadoras, com apuraÃ§Ã£o correta de custos e tributos.',
            'imagem': 'especialidades/construcao-civil.jpg',
            'ordem': 6,
            'ativo': True,
        },
    ]
    
    for esp_data in especialidades_data:
        esp, created = Especialidade.objects.get_or_create(
            titulo=esp_data['titulo'],
            defaults=esp_data
        )
        if created:
            print(f"  âœ“ Especialidade criada: {esp.titulo}")
        else:
            print(f"  - Especialidade jÃ¡ existe: {esp.titulo}")
    
    print("\nâœ… Dados de exemplo criados com sucesso!")
    print("\nResumo:")
    print(f"  - {Usuario.objects.count()} usuÃ¡rios")
    print(f"  - {PostBlog.objects.count()} posts")
    print(f"  - {Ebook.objects.count()} ebooks")
    print(f"  - {Evento.objects.count()} eventos")
    print(f"  - {Especialidade.objects.count()} especialidades")

if __name__ == '__main__':
    create_sample_data()
