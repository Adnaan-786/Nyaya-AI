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
    access_token_expire_minutes: int = Field(default=60)

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

    # s3_endpoint: str
    # s3_access_key: str
    # s3_secret_key: str
    # s3_bucket: str

    # =====================================================
    # External Services
    # =====================================================

    fake_mode: bool = Field(default=True)

    ocr_provider: str = Field(default="tesseract")
    llm_provider: str = Field(default="openai")

    # =====================================================
    # Monitoring
    # =====================================================

    sentry_dsn: str = Field(default="")
    log_level: str = Field(default="INFO")


@lru_cache
def get_settings() -> Settings:
    """
    Returns a cached Settings instance.

    This ensures environment variables are parsed only once
    during the application lifetime.
    """
    return Settings()