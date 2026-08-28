from tempfile import TemporaryDirectory
from unittest import mock

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import JobApplication


def _pdf_valido():
    import io

    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument.new()
    pdf.new_page(300, 300)
    buf = io.BytesIO()
    pdf.save(buf)
    return buf.getvalue()


class SubmitJobApplicationTests(TestCase):
    """ValidaÃ§Ãµes de seguranÃ§a do upload de currÃ­culo em Trabalhe Conosco."""

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
            'nome': 'JoÃ£o da Silva',
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
        payload = {'nome': 'JoÃ£o da Silva', 'email': 'joao@email.com', 'curriculo': arquivo}
        with mock.patch('core.api_views._verifica_recaptcha', return_value=False):
            resp = self.client.post(reverse('api_job_application'), payload)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(JobApplication.objects.count(), 0)

    def test_verifica_recaptcha_sem_secret_aceita(self):
        from core import api_views
        self.assertTrue(api_views._verifica_recaptcha(''))

    def test_honeypot_preenchido_descarta_silenciosamente(self):
        arquivo = SimpleUploadedFile('curriculo.pdf', _pdf_valido(), content_type='application/pdf')
        payload = {'nome': 'JoÃ£o da Silva', 'email': 'joao@email.com', 'website': 'http://spam.link'}
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


