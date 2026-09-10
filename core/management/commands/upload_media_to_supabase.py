"""
Management command to upload existing media files to Supabase Storage.
"""
import os
from django.core.management.base import BaseCommand
from django.conf import settings
from supabase import create_client


class Command(BaseCommand):
    help = 'Upload existing media files to Supabase Storage'

    def handle(self, *args, **options):
        url = settings.SUPABASE_URL
        key = settings.SUPABASE_SERVICE_KEY
        bucket = settings.SUPABASE_STORAGE_BUCKET
        media_root = settings.MEDIA_ROOT

        if not url or not key:
            self.stderr.write(self.style.ERROR(
                'SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in environment variables.'
            ))
            return

        client = create_client(url, key)

        # Create bucket if it doesn't exist
        try:
            client.storage.get_bucket(bucket)
            self.stdout.write(f'Bucket "{bucket}" already exists.')
        except Exception:
            client.storage.create_bucket(bucket)
            self.stdout.write(self.style.SUCCESS(f'Created bucket "{bucket}".'))

        # Ensure bucket is public so the frontend can access files directly
        client.storage.update_bucket(bucket, {'public': True})

        # Upload all files
        uploaded = 0
        for root, dirs, files in os.walk(media_root):
            for file in files:
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, media_root)
                # Normalize path separators for Supabase
                supabase_path = relative_path.replace('\\', '/')

                try:
                    with open(file_path, 'rb') as f:
                        file_bytes = f.read()
                    client.storage.from_(bucket).upload(
                        path=supabase_path,
                        file=file_bytes,
                        file_options={"content-type": self._guess_content_type(file_path)},
                    )
                    uploaded += 1
                    self.stdout.write(f'  Uploaded: {supabase_path}')
                except Exception as e:
                    self.stderr.write(self.style.WARNING(f'  Failed: {supabase_path} - {e}'))

        self.stdout.write(self.style.SUCCESS(f'\nDone! Uploaded {uploaded} files.'))

    def _guess_content_type(self, file_path):
        from core.mime import guess_content_type
        return guess_content_type(file_path)
