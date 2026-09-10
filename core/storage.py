"""
Custom Django storage backend for Supabase Storage.
"""
import os
from django.core.files.storage import Storage
from django.conf import settings
from supabase import create_client, Client


class SupabaseStorage(Storage):
    """Django storage backend that uses Supabase Storage."""

    def __init__(self, bucket_name=None):
        self.bucket_name = bucket_name or getattr(settings, 'SUPABASE_STORAGE_BUCKET', 'media')
        self.client = self._get_client()

    def _get_client(self) -> Client:
        url = getattr(settings, 'SUPABASE_URL', os.environ.get('SUPABASE_URL', ''))
        key = getattr(settings, 'SUPABASE_SERVICE_KEY', os.environ.get('SUPABASE_SERVICE_KEY', ''))
        return create_client(url, key)

    def _open(self, name, mode='rb'):
        from django.core.files.base import ContentFile
        response = self.client.storage.from_(self.bucket_name).download(name)
        return ContentFile(response)

    def _save(self, name, content):
        content.seek(0)
        file_bytes = content.read()
        self.client.storage.from_(self.bucket_name).upload(
            path=name,
            file=file_bytes,
            file_options={"content-type": self._guess_content_type(name)},
        )
        return name

    def delete(self, name):
        try:
            self.client.storage.from_(self.bucket_name).remove([name])
        except Exception:
            pass

    def exists(self, name):
        try:
            self.client.storage.from_(self.bucket_name).info(name)
            return True
        except Exception:
            return False

    def listdir(self, path):
        try:
            response = self.client.storage.from_(self.bucket_name).list(path)
            directories = [f['name'] for f in response if f.get('id') is None]
            files = [f['name'] for f in response if f.get('id') is not None]
            return directories, files
        except Exception:
            return [], []

    def url(self, name):
        supabase_url = getattr(settings, 'SUPABASE_URL', os.environ.get('SUPABASE_URL', ''))
        public_url = f"{supabase_url}/storage/v1/object/public/{self.bucket_name}/{name}"
        return public_url

    def size(self, name):
        try:
            response = self.client.storage.from_(self.bucket_name).list('')
            for f in response:
                if f['name'] == name:
                    return f.get('metadata', {}).get('size', 0)
        except Exception:
            pass
        return 0

    def _guess_content_type(self, name):
        from core.mime import guess_content_type
        return guess_content_type(name)
