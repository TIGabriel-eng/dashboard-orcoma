import json
import re

from django.core import mail
from django.test import Client, TestCase

from .models import NewsletterInscricao, PostBlog


def _inscrever(email, **extra):
    data = {'email': email, **extra}
    return Client().post('/api/newsletter/', data=json.dumps(data), content_type='application/json')


def _link_descadastro(texto):
    return re.search(r'/api/newsletter/descadastrar/\?t=([^\s]+)', texto).group(0)


class NewsletterEmailsTest(TestCase):
    def test_cadastro_envia_boas_vindas_com_link_de_descadastro(self):
        resposta = _inscrever('cliente@example.com', nome='Ana')

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['cliente@example.com'])
        self.assertIn('Olá, Ana!', mail.outbox[0].body)
        self.assertIn('/api/newsletter/descadastrar/?t=', mail.outbox[0].body)

    def test_cadastro_repetido_de_assinante_ativo_nao_envia_outro_email(self):
        _inscrever('cliente@example.com')
        _inscrever('cliente@example.com')

        self.assertEqual(len(mail.outbox), 1)

    def test_descadastrar_pelo_link_desativa_e_novo_cadastro_reativa(self):
        _inscrever('cliente@example.com')
        link = _link_descadastro(mail.outbox[0].body)

        resposta = self.client.get(link)
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(NewsletterInscricao.objects.get(email='cliente@example.com').ativo)

        _inscrever('cliente@example.com')
        self.assertTrue(NewsletterInscricao.objects.get(email='cliente@example.com').ativo)
        self.assertEqual(len(mail.outbox), 2)

    def test_link_de_descadastro_adulterado_nao_funciona(self):
        resposta = self.client.get('/api/newsletter/descadastrar/?t=invalido')

        self.assertEqual(resposta.status_code, 400)

    def test_post_publicado_avisa_so_assinantes_ativos(self):
        ativo = NewsletterInscricao.objects.create(email='ativo@example.com')
        NewsletterInscricao.objects.create(email='cancelado@example.com', ativo=False)
        mail.outbox = []

        with self.captureOnCommitCallbacks(execute=True):
            PostBlog.objects.create(titulo='Reforma tributária', slug='reforma', conteudo='<p>x</p>', status='publicado')

        destinatarios = [m.to[0] for m in mail.outbox]
        self.assertEqual(destinatarios, [ativo.email])
        self.assertIn('#/blog-post/reforma', mail.outbox[0].body)
        self.assertEqual(mail.outbox[0].subject, 'Novo no blog: Reforma tributária')

    def test_rascunho_nao_avisa_e_editar_post_ja_publicado_nao_reenvia(self):
        NewsletterInscricao.objects.create(email='ativo@example.com')
        mail.outbox = []

        with self.captureOnCommitCallbacks(execute=True):
            post = PostBlog.objects.create(titulo='Rascunho', slug='rascunho', conteudo='<p>x</p>', status='rascunho')
        self.assertEqual(len(mail.outbox), 0)

        with self.captureOnCommitCallbacks(execute=True):
            post.status = 'publicado'
            post.save()
            post.titulo = 'Título corrigido'
            post.save()
        self.assertEqual(len(mail.outbox), 1)
