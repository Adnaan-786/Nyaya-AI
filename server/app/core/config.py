"""Environment-driven settings (12-factor, C.3.4)."""

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "local"
    debug: bool = True

    database_url: str = "postgresql+asyncpg://nyaya@/nyayaai?host=/tmp&port=5433"

    database_requires_ssl: bool = False

    @model_validator(mode="after")
    def _normalise_database_url(self) -> "Settings":
        url = self.database_url
        # Remember if SSL was requested before stripping query params.
        self.database_requires_ssl = "sslmode=" in url or "ssl=" in url
        # Strip query params — asyncpg rejects libpq-only keys like
        # sslmode, channel_binding, etc. SSL is passed via connect_args.
        url = url.split("?")[0]
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://") and "+asyncpg" not in url:
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        self.database_url = url
        return self

    # B.4.3: 30-minute access token, 30-day refresh with rotation.
    jwt_secret: str = "dev-only-change-in-staging"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30
    refresh_token_days: int = 30

    # C.2: every integration honours FAKE_MODE so the whole stack runs offline.
    # This is what lets the demo work regardless of which third-party approvals
    # (NAPIX, DLT registration for SMS, Razorpay KYC) have actually landed.
    fake_mode: bool = True

    msg91_auth_key: str | None = None
    msg91_template_id: str | None = None
    ecourts_api_key: str | None = None
    indiankanoon_api_key: str | None = None
    # Kept for app/integrations/ocr.py's scanned-document gate, which only checks
    # whether *some* AI provider looks configured — that path is independently
    # unimplemented (Document AI was never wired) regardless of which LLM answers
    # summarize/research, so this staying unset even with Grok configured is fine.
    anthropic_api_key: str | None = None

    grok_api_key: str | None = None
    # Verify this against xAI's current model catalog (console.x.ai) before relying
    # on it — override via GROK_MODEL if it's changed since this was written.
    grok_model: str = "grok-4"

    s3_bucket: str | None = None
    aws_region: str = "ap-south-1"
    # Set for any S3-compatible provider that isn't AWS itself (Cloudflare R2, etc.) —
    # e.g. https://<account_id>.r2.cloudflarestorage.com. Left unset, boto3 talks to
    # real AWS S3 exactly as before.
    s3_endpoint_url: str | None = None

    razorpay_key_id: str | None = None
    razorpay_key_secret: str | None = None
    # Separate from the API secret: webhooks are unauthenticated HTTP, and this
    # signature is the only thing preventing a stranger marking invoices paid.
    razorpay_webhook_secret: str | None = None

    # FCM HTTP v1. The service-account JSON path, not a legacy server key — the
    # `key=AAAA...` endpoint was decommissioned in 2024.
    firebase_project_id: str | None = None
    firebase_credentials_path: str | None = None

    # Storage root used when S3 is not configured (local demo).
    local_storage_dir: str = "./storage"

    max_upload_bytes: int = 50 * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
