from enum import StrEnum
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
import os


class Environment(StrEnum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # =====================================================
    # Application
    # =====================================================

    app_name: str = Field(default="NyayaAI Server")
    environment: Environment = Field(default=Environment.DEVELOPMENT)
    debug: bool = Field(default=True)

    api_version: str = Field(default="v1")
    api_prefix: str = Field(default="/v1")

    # =====================================================
    # Security
    # =====================================================

    secret_key: str = Field(..., min_length=32)
    jwt_algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=30)
    refresh_token_expire_days: int = Field(default=30)

    # =====================================================
    # OTP / Auth
    # =====================================================

    otp_length: int = Field(default=6)
    otp_expire_minutes: int = Field(default=5)
    otp_max_per_hour: int = Field(default=3)
    otp_max_verify_attempts: int = Field(default=5)

    # =====================================================
    # Database
    # =====================================================

    database_url: str

    # =====================================================
    # Redis
    # =====================================================

    redis_url: str
    

    # =====================================================
    # Storage
    # =====================================================

    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_bucket: str

    s3_endpoint: str
    s3_access_key: str
    s3_secret_key: str
    s3_bucket: str

    # =====================================================
    # External Services
    # =====================================================

    fake_mode: bool = Field(default=True)

    ocr_provider: str = Field(default="tesseract")
    llm_provider: str = Field(default="openai")

    # =====================================================
    # eCourts sync (module M5)
    # =====================================================

    # "fixture" (recorded responses, safe for local/staging/CI),
    # "napix" (official NIC API, once approved), or
    # "commercial" (eCourtsIndia/Surepass fallback).
    ecourts_provider: str = Field(default="fixture")
    ecourts_lookup_cache_hours: int = Field(default=24)
    ecourts_lookup_timeout_seconds: float = Field(default=5.0)
    ecourts_sync_rate_limit_per_hour: int = Field(default=1)
    ecourts_max_consecutive_failures: int = Field(default=3)
    napix_api_key: str = Field(default="")
    commercial_ecourts_api_key: str = Field(default="")

    # =====================================================
    # Document Pipeline (module M6)
    # =====================================================

    document_max_upload_bytes: int = Field(default=50 * 1024 * 1024)  # 50 MB, contract B.9
    document_allowed_mime_types: str = Field(
        default=(
            "application/pdf,image/jpeg,image/png,"
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
    )
    document_upload_url_expiry_seconds: int = Field(default=900)  # 15 min, contract B.9
    document_download_url_expiry_seconds: int = Field(default=900)  # 15 min, contract B.6

    document_chunk_words: int = Field(default=600)  # ~800 tokens (plan C.8)
    document_chunk_overlap_words: int = Field(default=80)

    embedding_provider: str = Field(default="fake")  # fake|openai
    embedding_dimensions: int = Field(default=1536)
    openai_api_key: str = Field(default="")

    # =====================================================
    # Monitoring
    # =====================================================

    sentry_dsn: str = Field(default="")
    log_level: str = Field(default="INFO")

    @property
    def document_allowed_mime_type_set(self) -> set[str]:
        return {m.strip() for m in self.document_allowed_mime_types.split(",") if m.strip()}


@lru_cache
def get_settings() -> Settings:
    """
    Returns a cached Settings instance.

    This ensures environment variables are parsed only once
    during the application lifetime.
    """
    return Settings()

