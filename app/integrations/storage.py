"""
S3-compatible object storage (MinIO locally, AWS S3 in staging/prod --
same API, per plan C.1 "Storage: AWS S3 (ap-south-1), SSE-KMS").

Presigned URL generation is pure local signing (no network round
trip), so it's safe to call synchronously from async route handlers.
"""

from functools import lru_cache
from uuid import UUID

import boto3
from botocore.client import Config as BotoConfig

from app.config import get_settings

settings = get_settings()


@lru_cache
def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.minio_endpoint,
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
        config=BotoConfig(signature_version="s3v4", s3={"addressing_style": "path"}),
        region_name="ap-south-1",
    )


def object_key_for(tenant_id: UUID, document_id: UUID, filename: str) -> str:
    """
    Per-tenant key prefix (plan C.1: "Storage ... Per-tenant key
    prefixes"), matching plan C.8: tenants/{tenant_id}/documents/{doc_id}.
    """
    safe_name = filename.replace("/", "_").replace("\\", "_")
    return f"tenants/{tenant_id}/documents/{document_id}/{safe_name}"


def ensure_bucket_exists() -> None:
    client = get_s3_client()
    try:
        client.head_bucket(Bucket=settings.minio_bucket)
    except Exception:
        client.create_bucket(Bucket=settings.minio_bucket)


def generate_presigned_upload_url(key: str, content_type: str) -> str:
    client = get_s3_client()
    return client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.minio_bucket,
            "Key": key,
            "ContentType": content_type,
        },
        ExpiresIn=settings.document_upload_url_expiry_seconds,
    )


def generate_presigned_download_url(key: str, *, filename: str | None = None) -> str:
    client = get_s3_client()
    params = {"Bucket": settings.minio_bucket, "Key": key}
    if filename:
        params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'
    return client.generate_presigned_url(
        "get_object",
        Params=params,
        ExpiresIn=settings.document_download_url_expiry_seconds,
    )


def get_object_bytes(key: str) -> bytes:
    client = get_s3_client()
    obj = client.get_object(Bucket=settings.minio_bucket, Key=key)
    return obj["Body"].read()


def put_object_bytes(key: str, data: bytes, *, content_type: str) -> None:
    """
    Direct (non-presigned) upload for server-generated files -- e.g.
    module M7's draftsman DOCX output. Distinct from the presigned-PUT
    flow in request_upload_url, which is for client-uploaded documents
    (contract B.9).
    """
    client = get_s3_client()
    client.put_object(
        Bucket=settings.minio_bucket, Key=key, Body=data, ContentType=content_type
    )


def delete_object(key: str) -> None:
    client = get_s3_client()
    client.delete_object(Bucket=settings.minio_bucket, Key=key)
