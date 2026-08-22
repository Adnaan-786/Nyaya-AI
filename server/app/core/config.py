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
    # One template ID per message the product sends, because India's DLT regime binds
    # each approved body to its own ID — there is no "send arbitrary text" call to
    # share. See app/integrations/sms.py for the exact bodies these must be registered
    # with; a mismatch is rejected by the operator, not delivered with a warning.
    msg91_template_id: str | None = None  # OTP
    msg91_template_client_invite: str | None = None
    msg91_template_invoice: str | None = None
    # Optional: the DLT-approved 6-character header (sender ID). MSG91 falls back to the
    # one attached to the template on its panel when this is unset, which is the common
    # case — set it only if the account requires it explicitly.
    msg91_sender_id: str | None = None
    ecourts_api_key: str | None = None
    indiankanoon_api_key: str | None = None
    # Only consumer is the `anthropic` LLM provider below. OCR used to check this too,
    # as a proxy for "does any AI look configured" — it no longer does, because OCR now
    # has providers of its own with their own credentials (see `ocr_provider`).
    anthropic_api_key: str | None = None

    # Groq (groq.com) — fast inference hosting for open models, and easily confused
    # with Grok (x.ai)'s unrelated model of a near-identical name. A key that starts
    # `gsk_` is Groq; xAI's start `xai-`. Check console.groq.com if this default
    # model has been retired before relying on it.
    groq_api_key: str | None = None
    groq_model: str = "llama-3.3-70b-versatile"

    # Which backend answers summarize/research/draft/risk-review: fake | groq |
    # anthropic. Defaults to groq because that is what the deployed instance runs on
    # — changing this default would silently repoint production at another vendor.
    # `fake` is not only a test seam: an unconfigured provider degrades to it rather
    # than 500ing, so the demo stays usable before any key is provisioned.
    llm_provider: str = "groq"
    # Anthropic only. Groq's model is `groq_model` above, because the two providers'
    # model catalogues have nothing to do with each other and a single field would
    # mean re-editing it every time the provider is switched.
    llm_model: str = "claude-sonnet-4-6"
    llm_max_tokens: int = 4096

    # C.7: per-tenant concurrency cap and daily quota. Per-plan overrides live in
    # app/api/ai.py's DAILY_JOB_LIMITS until the billing module owns them; these are
    # the flat fallbacks.
    ai_max_concurrent_jobs_per_tenant: int = 3
    ai_daily_job_quota_per_tenant: int = 50

    # C.9 per-job-type timeouts. A summary of a 40-page scan legitimately takes
    # minutes; a research answer that has not landed in two is not coming.
    ai_summarize_timeout_seconds: int = 300
    ai_research_timeout_seconds: int = 120
    ai_draft_timeout_seconds: int = 180
    ai_risk_review_timeout_seconds: int = 180

    # Document pipeline (C.8). Separate from `max_upload_bytes` below, which caps
    # every upload; this one is the document-specific limit B.9 states. The smaller of
    # the two wins — see app/services/document_service.py::upload_limit_bytes.
    document_max_upload_bytes: int = 50 * 1024 * 1024
    document_allowed_mime_types: str = (
        "application/pdf,image/jpeg,image/png,"
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    # B.9/B.6: presigned URLs are the only way bytes move, so their lifetime is the
    # window in which a leaked link is useful. 15 minutes is long enough for a slow
    # mobile upload and short enough that a link pasted into a chat expires.
    document_upload_url_expiry_seconds: int = 900
    document_download_url_expiry_seconds: int = 900

    # ~800 tokens per chunk (C.8), with enough overlap that a sentence spanning a
    # boundary is still retrievable from one side of it.
    document_chunk_words: int = 600
    document_chunk_overlap_words: int = 80

    embedding_provider: str = "fake"
    embedding_dimensions: int = 1536
    openai_api_key: str | None = None

    # Which provider answers image and scanned-PDF OCR: auto | document_ai | tesseract
    # | none. `auto` is the C.1 chain — Document AI first, local Tesseract behind it.
    # Pin it to one when a provider is configured but misbehaving, so a Document AI
    # outage surfaces as failures instead of hiding behind worse local results.
    # PDFs that carry their own text layer never reach any of these.
    ocr_provider: str = "auto"
    document_ai_project_id: str | None = None
    # Part of the API hostname as well as the resource path — a mismatch here is a 404
    # on a processor that plainly exists.
    document_ai_location: str = "us"
    document_ai_processor_id: str | None = None
    # Service-account JSON for Document AI. Deliberately not `firebase_credentials_path`
    # below: these are different service accounts with different scopes, and sharing one
    # would hand the push credential read access to every uploaded document.
    google_credentials_path: str | None = None

    # Transactional email (OTP login). Two delivery paths:
    #
    #  1. BREVO_API_KEY — uses Brevo's HTTP API over port 443. Required on hosts
    #     like Render that block outbound SMTP ports (25/465/587).
    #  2. SMTP_* — standard SMTP, works with any provider. Use on hosts that
    #     allow outbound SMTP (a VPS, Railway, Fly, etc.).
    #
    # If both are set, the HTTP path wins (faster, no port issues).
    brevo_api_key: str | None = None
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    # Must be an address the provider has verified, or the relay will accept the
    # login and then reject the message.
    smtp_from: str | None = None

    # Browser origins allowed to call this API (the tools/api-console test page, and
    # whatever host it is served from). Comma-separated.
    #
    # Deliberately a list rather than "*": this API answers with privileged client data,
    # and while bearer auth means a hostile page cannot ride an existing session the way
    # it could with cookies, there is no reason for any origin but ours to be able to
    # reach it from a browser at all.
    cors_origins: str = "http://localhost:8080,http://127.0.0.1:8080"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def document_allowed_mime_type_set(self) -> set[str]:
        return {m.strip() for m in self.document_allowed_mime_types.split(",") if m.strip()}

    # Opt-in placeholder OCR text for scanned documents. Off even under FAKE_MODE,
    # because ocr_status is rendered to the user as a claim about whether a document is
    # searchable — see run_providers() in app/integrations/ocr/factory.py.
    ocr_fake_text: bool = False

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
