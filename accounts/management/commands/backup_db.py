import gzip
import io
import os
import subprocess
from datetime import datetime

from django.core.management.base import BaseCommand

import logging
logger = logging.getLogger("talentiq")


class Command(BaseCommand):
    help = "Backup PostgreSQL database to Cloudflare R2"

    def handle(self, *args, **options):
        database_url = os.environ.get("DATABASE_URL", "")
        if not database_url:
            self.stderr.write("DATABASE_URL not set — skipping backup")
            return

        timestamp = datetime.utcnow().strftime("%Y-%m-%d_%H%M")
        filename = f"talentiq_backup_{timestamp}.sql.gz"

        self.stdout.write(f"Starting DB backup: {filename}")

        try:
            result = subprocess.run(
                ["pg_dump", database_url, "--no-owner", "--no-acl"],
                capture_output=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            self.stderr.write(f"pg_dump failed: {e.stderr.decode()}")
            return
        except FileNotFoundError:
            self.stderr.write("pg_dump not found — postgresql-client not installed")
            return

        compressed = io.BytesIO()
        with gzip.GzipFile(fileobj=compressed, mode="wb") as gz:
            gz.write(result.stdout)
        compressed.seek(0)

        from talentiq.storage import upload_to_r2
        url = upload_to_r2(compressed, "backups", filename)

        if url:
            self.stdout.write(self.style.SUCCESS(f"Backup complete: {url}"))
        else:
            self.stderr.write("R2 upload failed — check R2 env vars")
