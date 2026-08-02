import uuid
import logging

logger = logging.getLogger("talentiq")


def upload_to_r2(file_obj, folder: str, original_name: str) -> str:
    """
    Upload a file to Cloudflare R2. Returns the public URL, or "" on any failure.
    Never raises — file storage must never block the main workflow.
    """
    try:
        from django.conf import settings
        account_id = getattr(settings, "R2_ACCOUNT_ID", "")
        access_key = getattr(settings, "R2_ACCESS_KEY_ID", "")
        secret_key = getattr(settings, "R2_SECRET_ACCESS_KEY", "")
        bucket = getattr(settings, "R2_BUCKET_NAME", "")
        public_base = getattr(settings, "R2_PUBLIC_BASE_URL", "").rstrip("/")

        if not all([account_id, access_key, secret_key, bucket, public_base]):
            return ""

        import boto3
        from botocore.config import Config

        s3 = boto3.client(
            "s3",
            endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(signature_version="s3v4"),
            region_name="auto",
        )

        safe_name = "".join(c for c in original_name if c.isalnum() or c in "._-")[:100]
        key = f"{folder}/{uuid.uuid4().hex}/{safe_name}"
        content_type = "application/pdf" if safe_name.lower().endswith(".pdf") else "application/octet-stream"

        file_obj.seek(0)
        s3.upload_fileobj(file_obj, bucket, key, ExtraArgs={"ContentType": content_type})

        return f"{public_base}/{key}"

    except Exception as e:
        logger.warning(f"R2 upload failed (non-fatal): {e}")
        return ""
