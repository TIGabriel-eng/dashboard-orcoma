from tempfile import TemporaryDirectory
from unittest import mock

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import JobApplication
from core import security
from core.models import IPSuspeito, SecurityEvent


def _pdf_valido():
    import io

    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument.new()
    pdf.new_page(300, 300)
    buf = io.BytesIO()
    pdf.save(buf)
    return buf.getvalue()


class SubmitJobApplicationTests(TestCase):
    """Validações de segurança do upload de currículo em Trabalhe Conosco."""

    tempdir = None

    @classmethod
    def setUpClass(cls):
        cls.tempdir = TemporaryDirectory()
        cls.overrider = override_settings(MEDIA_ROOT=cls.tempdir.name)
        cls.overrider.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        cls.overrider.disable()
        cls.tempdir.cleanup()
        super().tearDownClass()

    def setUp(self):
        cache.clear()

    def _post(self, curriculo=None, recaptcha_ok=True):
        payload = {
            'nome': 'João da Silva',
            'email': 'joao@email.com',
            'g-recaptcha-response': 'token-valido' if recaptcha_ok else 'token-invalido',
        }
        if curriculo is not None:
            payload['curriculo'] = curriculo
        with mock.patch('core.api_views._verifica_recaptcha', return_value=recaptcha_ok):
            return self.client.post(reverse('api_job_application'), payload)

    def test_aceita_pdf(self):
        arquivo = SimpleUploadedFile('curriculo.pdf', b'%PDF-1.4\nconteudo', content_type='application/pdf')
        resp = self._post(arquivo)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(JobApplication.objects.count(), 1)

    def test_aceita_docx(self):
        arquivo = SimpleUploadedFile(
            'curriculo.docx',
            b'PK\x03\x04zipcontainer',
            content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        )
        resp = self._post(arquivo)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(JobApplication.objects.count(), 1)

    def test_rejeita_html_renomeado_pdf(self):
        arquivo = SimpleUploadedFile('malicioso.pdf', b'<html><script>alert(1)</script></html>', content_type='application/pdf')
        resp = self._post(arquivo)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(JobApplication.objects.count(), 0)

    def test_rejeita_extensao_nao_permitida(self):
        arquivo = SimpleUploadedFile('malicioso.exe', b'%PDF-1.4', content_type='application/octet-stream')
        resp = self._post(arquivo)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(JobApplication.objects.count(), 0)

    def test_rejeita_magic_incompativel_com_extensao(self):
        arquivo = SimpleUploadedFile('curriculo.docx', b'%PDF-1.4\nconteudo', content_type='application/pdf')
        resp = self._post(arquivo)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(JobApplication.objects.count(), 0)

    def test_rejeita_arquivo_muito_grande(self):
        arquivo = SimpleUploadedFile('curriculo.pdf', b'%PDF-1.4\n' + b'0' * (6 * 1024 * 1024), content_type='application/pdf')
        resp = self._post(arquivo)
        self.assertEqual(resp.status_code, 413)
        self.assertEqual(JobApplication.objects.count(), 0)

    def test_curriculo_obrigatorio(self):
        resp = self._post(None)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(JobApplication.objects.count(), 0)

    def test_rejeita_recaptcha_invalido(self):
        arquivo = SimpleUploadedFile('curriculo.pdf', _pdf_valido(), content_type='application/pdf')
        resp = self._post(arquivo, recaptcha_ok=False)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(JobApplication.objects.count(), 0)

    def test_rejeita_sem_token_recaptcha(self):
        arquivo = SimpleUploadedFile('curriculo.pdf', _pdf_valido(), content_type='application/pdf')
        payload = {'nome': 'João da Silva', 'email': 'joao@email.com', 'curriculo': arquivo}
        with mock.patch('core.api_views._verifica_recaptcha', return_value=False):
            resp = self.client.post(reverse('api_job_application'), payload)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(JobApplication.objects.count(), 0)

    def test_verifica_recaptcha_sem_secret_aceita(self):
        from core import api_views
        self.assertTrue(api_views._verifica_recaptcha(''))

    def test_honeypot_preenchido_descarta_silenciosamente(self):
        arquivo = SimpleUploadedFile('curriculo.pdf', _pdf_valido(), content_type='application/pdf')
        payload = {'nome': 'João da Silva', 'email': 'joao@email.com', 'website': 'http://spam.link'}
        payload['curriculo'] = arquivo
        resp = self.client.post(reverse('api_job_application'), payload)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(JobApplication.objects.count(), 0)

    def test_pdf_gera_preview(self):
        arquivo = SimpleUploadedFile('curriculo.pdf', _pdf_valido(), content_type='application/pdf')
        resp = self._post(arquivo)
        self.assertEqual(resp.status_code, 200)
        candidatura = JobApplication.objects.get()
        self.assertTrue(candidatura.preview)
        self.assertTrue(candidatura.preview.name.endswith('.png'))

    def test_docx_nao_gera_preview(self):
        arquivo = SimpleUploadedFile(
            'curriculo.docx',
            b'PK\x03\x04zipcontainer',
            content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        )
        resp = self._post(arquivo)
        self.assertEqual(resp.status_code, 200)
        candidatura = JobApplication.objects.get()
        self.assertFalse(candidatura.preview)

    def test_pdf_invalido_nao_derruba_candidatura(self):
        arquivo = SimpleUploadedFile('curriculo.pdf', b'%PDF-1.4\nconteudo', content_type='application/pdf')
        resp = self._post(arquivo)
        self.assertEqual(resp.status_code, 200)
        candidatura = JobApplication.objects.get()
        self.assertFalse(candidatura.preview)


class SecurityMonitorTests(TestCase):
    """Detecção automática de acessos suspeitos (middleware + módulo security)."""

    def setUp(self):
        cache.clear()
        SecurityEvent.objects.all().delete()
        IPSuspeito.objects.all().delete()

    def tearDown(self):
        cache.clear()

    def _headers(self, ip='198.51.100.10', ua='Mozilla/5.0 (Windows NT 10.0; Win64; x64)'):
        return {
            'HTTP_X_FORWARDED_FOR': ip,
            'HTTP_USER_AGENT': ua,
            'HTTP_HOST': 'testserver',
        }

    def test_detecta_path_de_scanner(self):
        self.client.get('/.env', **self._headers())
        self.assertEqual(SecurityEvent.objects.filter(tipo='path_invasivo').count(), 1)
        self.assertTrue(IPSuspeito.objects.filter(ip_address='198.51.100.10', resolvido=False).exists())

    def test_detecta_tentativa_de_injecao(self):
        self.client.get('/api/posts/?id=1%20UNION%20SELECT%201', **self._headers())
        self.assertEqual(SecurityEvent.objects.filter(tipo='injecao').count(), 1)
        self.assertTrue(IPSuspeito.objects.filter(ip_address='198.51.100.10').exists())

    def test_detecta_user_agent_suspeito(self):
        self.client.get('/', **self._headers(ip='198.51.100.11', ua='sqlmap/1.7.0'))
        self.assertEqual(SecurityEvent.objects.filter(tipo='user_agent_suspeito').count(), 1)
        self.assertTrue(IPSuspeito.objects.filter(ip_address='198.51.100.11').exists())

    def test_detecta_path_traversal(self):
        self.client.get('/../../etc/passwd', **self._headers(ip='198.51.100.12'))
        self.assertEqual(SecurityEvent.objects.filter(tipo='injecao').count(), 1)

    def test_acesso_normal_nao_gera_evento(self):
        self.client.get('/', **self._headers())
        self.client.get('/api/posts/', **self._headers())
        self.assertEqual(SecurityEvent.objects.count(), 0)
        self.assertEqual(IPSuspeito.objects.count(), 0)

    def test_ip_local_nao_dispara_alarme(self):
        # Em desenvolvimento o visitante é o próprio dono (localhost).
        self.client.get('/.env', HTTP_HOST='127.0.0.1')  # REMOTE_ADDR padrão é 127.0.0.1
        self.assertEqual(SecurityEvent.objects.count(), 0)
        self.assertEqual(IPSuspeito.objects.count(), 0)

    def test_alertas_nao_quebram_requests(self):
        resp = self.client.get('/api/posts/', **self._headers(ip='198.51.100.13', ua='curl/7.0'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(SecurityEvent.objects.filter(tipo='user_agent_suspeito').count(), 1)

    def test_marca_e_reverte_ip_suspeito(self):
        v1 = security.marcar_ip_suspeito('198.51.100.20', '[teste] atividade anômala', nivel=2)
        v2 = security.marcar_ip_suspeito('198.51.100.20', '[teste] outro motivo', nivel=3)
        ip = IPSuspeito.objects.get(ip_address='198.51.100.20')
        self.assertTrue(v1)
        self.assertFalse(v2)  # já estava marcado (não é "novo alerta")
        self.assertIn('outro motivo', ip.motivo)
        ip.resolvido = True
        ip.save(update_fields=['resolvido'])
        self.assertFalse(security.ip_e_suspeito('198.51.100.20'))

    def test_ip_local_nao_e_marcado_manualmente(self):
        self.assertFalse(security.marcar_ip_suspeito('127.0.0.1', '[teste]'))
        self.assertFalse(IPSuspeito.objects.filter(ip_address='127.0.0.1').exists())

    def test_enviar_alerta_sem_email_configurado_nao_quebra(self):
        # Sem ALERT_EMAIL_TO, o alerta só loga (comportamento seguro por padrão).
        security.registrar_evento('injecao', '198.51.100.30', '/', 'ua', 'teste')
        self.assertEqual(SecurityEvent.objects.filter(ip_address='198.51.100.30').count(), 1)
        meta = resp.wsgi_request.META
        print('XFF presente:', 'HTTP_X_FORWARDED_FOR' in meta)
        print('REMOTE_ADDR:', meta.get('REMOTE_ADDR'))
        print('XFF valor:', meta.get('HTTP_X_FORWARDED_FOR'))
        print('request.path:', resp.wsgi_request.path)
        print('Eventos agora:', SecurityEvent.objects.count())
