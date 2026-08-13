from django.urls import path
from core import api_views

urlpatterns = [
    path('api/posts/', api_views.list_posts, name='api_posts'),
    path('api/posts/<slug:slug>/', api_views.detalhe_post, name='api_post_detalhe'),
    path('api/eventos/', api_views.list_eventos, name='api_eventos'),
    path('api/ebooks/', api_views.list_ebooks, name='api_ebooks'),
    path('api/ebooks/<slug:slug>/download/', api_views.baixar_ebook, name='api_ebook_download'),
    path('api/especialidades/', api_views.list_especialidades, name='api_especialidades'),
    path('api/carrossel/', api_views.list_carrossel, name='api_carrossel'),
    path('api/sobre-nos-fotos/', api_views.list_sobre_nos_fotos, name='api_sobre_nos_fotos'),
    path('api/especialidades/<slug:slug>/', api_views.detalhe_especialidade, name='api_especialidade_detalhe'),
    path('api/pageview/', api_views.record_pageview, name='api_pageview'),
    path('api/contact/', api_views.submit_contact, name='api_contact'),
    path('api/whatsapp-click/', api_views.track_whatsapp_click, name='api_whatsapp_click'),
    path('api/cliente/login/', api_views.login_cliente, name='api_cliente_login'),
    path('api/cliente/acesso/', api_views.registrar_acesso_cliente, name='api_cliente_acesso'),
    path('api/job-application/', api_views.submit_job_application, name='api_job_application'),
    path('api/newsletter/', api_views.subscribe_newsletter, name='api_newsletter'),
]
