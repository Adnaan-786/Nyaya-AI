"""Object storage with presigned uploads (B.9).

The app's flow is fixed by the contract: ask for an upload URL, PUT the bytes straight
to it, then confirm. That flow must not change depending on where the bytes land, so
both backends expose the same two operations and the same 15-minute signed URL.

* **S3** when a bucket is configured — the real path, per-tenant key prefixes (C.1).
* **Local disk** otherwise, with a signed URL pointing at our own PUT endpoint. This is
  not a stub: the app performs a genuine direct upload against a URL it cannot forge.

Keys are always `tenant/<tenant_id>/<document_id>/<filename>`, so a bucket listing can
never mix two firms' files and a leaked key reveals nothing about another tenant.
"""

import hashlib
import hmac
import logging
import time
from pathlib import Path

from app.core import envelope
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

UPLOAD_URL_TTL_SECONDS = 15 * 60

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def storage_key(tenant_id: str, document_id: str, filename: str) -> str:
    safe = Path(filename).name.replace("/", "_") or "file"
    return f"tenant/{tenant_id}/{document_id}/{safe}"


def sign(document_id: str, expires_at: int) -> str:
    payload = f"{document_id}:{expires_at}".encode()
    return hmac.new(settings.jwt_secret.encode(), payload, hashlib.sha256).hexdigest()


def verify_signature(document_id: str, expires_at: int, signature: str) -> None:
    """Rejects tampered and expired upload URLs.

    `compare_digest` rather than `==` because a timing-comparable check on an upload
    token is a real (if slow) forgery path.
    """
    if expires_at < int(time.time()):
        raise envelope.ApiError(
            403, "UPLOAD_URL_EXPIRED", "That upload link has expired. Please try again."
        )
    if not hmac.compare_digest(sign(document_id, expires_at), signature):
        # Deliberately not FORBIDDEN_ROLE: the app renders that as "your role does not
        # allow this", which is nonsense for a bad link. An unknown code falls back to
        # a generic toast (B.3), which is the honest behaviour here.
        raise envelope.ApiError(403, "UPLOAD_URL_INVALID", "This link is not valid.")


def build_upload_url(document_id: str) -> str:
    expires_at = int(time.time()) + UPLOAD_URL_TTL_SECONDS
    signature = sign(document_id, expires_at)
    return f"/v1/uploads/{document_id}?expires={expires_at}&signature={signature}"


def validate_upload(mime_type: str, size_bytes: int) -> None:
    if mime_type not in ALLOWED_MIME_TYPES:
        raise envelope.validation(
            "That file type is not supported.", {"mime_type": mime_type}
        )
    if size_bytes <= 0 or size_bytes > settings.max_upload_bytes:
        megabytes = settings.max_upload_bytes // (1024 * 1024)
        raise envelope.validation(
            f"Files must be smaller than {megabytes} MB.", {"size_bytes": str(size_bytes)}
        )


def _local_path(key: str) -> Path:
    path = Path(settings.local_storage_dir) / key
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _s3_client():
    import boto3  # imported lazily so local runs need no AWS SDK

    # `endpoint_url=None` talks to real AWS exactly as before; set it for any other
    # S3-compatible provider (Cloudflare R2, etc.) — boto3 treats a custom endpoint
    # the same way for every other call, which is the whole point of the API being
    # S3-compatible in the first place.
    return boto3.client(
        "s3", region_name=settings.aws_region, endpoint_url=settings.s3_endpoint_url
    )


async def put_object(key: str, data: bytes) -> None:
    if settings.s3_bucket:
        extra: dict = {}
        # SSE-KMS is an AWS-specific feature; a non-AWS endpoint (R2, etc.) doesn't
        # implement it and rejects the parameter outright.
        if not settings.s3_endpoint_url:
            extra["ServerSideEncryption"] = "aws:kms"
        _s3_client().put_object(Bucket=settings.s3_bucket, Key=key, Body=data, **extra)
        return
    _local_path(key).write_bytes(data)


async def get_object(key: str) -> bytes:
    if settings.s3_bucket:
        response = _s3_client().get_object(Bucket=settings.s3_bucket, Key=key)
        return response["Body"].read()

    path = _local_path(key)
    if not path.exists():
        raise envelope.not_found("document", "That file is no longer available.")
    return path.read_bytes()


async def delete_object(key: str) -> None:
    if settings.s3_bucket:
        _s3_client().delete_object(Bucket=settings.s3_bucket, Key=key)
        return
    path = _local_path(key)
    if path.exists():
        path.unlink()


def build_download_url(document_id: str) -> str:
    """B.5: download URLs are short-lived and must never be cached by the client."""
    expires_at = int(time.time()) + UPLOAD_URL_TTL_SECONDS
    signature = sign(document_id, expires_at)
    return f"/v1/documents/{document_id}/download?expires={expires_at}&signature={signature}"
