"""Auth request/response schemas.

Field names are snake_case on the wire, matching what the Android DTOs decode with
their snake_case naming strategy. FastAPI generates the OpenAPI document from these,
so these classes *are* the contract now that both sides are ours.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.phone import normalise_phone


class OtpRequest(BaseModel):
    phone: str = Field(examples=["+919812345678"])

    @field_validator("phone")
    @classmethod
    def normalise(cls, value: str) -> str:
        return normalise_phone(value)


class OtpVerifyRequest(OtpRequest):
    otp: str = Field(min_length=6, max_length=6)


class EmailOtpRequest(BaseModel):
    # EmailStr would need the email-validator package on the critical path of signing
    # in; pydantic's own constraint plus the relay's rejection is enough here, and the
    # address is lowercased so "A@b.com" and "a@b.com" cannot become two accounts.
    email: str = Field(min_length=5, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

    @field_validator("email")
    @classmethod
    def normalise_email(cls, value: str) -> str:
        return value.strip().lower()


class EmailOtpVerifyRequest(EmailOtpRequest):
    otp: str = Field(min_length=6, max_length=6)


class RefreshRequest(BaseModel):
    refresh_token: str


class OnboardRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    role_hint: str = Field(default="lawyer", pattern="^(lawyer|firm_admin)$")
    firm_name: str | None = None
    bar_council_id: str | None = None
    language: str = Field(default="en", pattern="^(en|hi)$")


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    # Optional since the email OTP channel landed — an account created by email has no
    # phone until its owner adds one, and serialising it as required would 500 on
    # exactly the accounts that channel creates.
    phone: str | None = None
    email: str | None = None
    role: str
    language: str
    created_at: datetime


class TokenPairOut(BaseModel):
    access_token: str
    refresh_token: str
    is_new_user: bool
    user: UserOut | None = None


class DeviceRegistration(BaseModel):
    fcm_token: str
    platform: str = "android"
    app_version: str | None = None


class DeviceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID


class AppConfigOut(BaseModel):
    """B.14. Unauthenticated, fetched on every cold start, cached 6h by the app."""

    min_supported_version: int
    latest_version: int
    feature_flags: dict[str, bool]
    status_banner: str | None = None
    support_phone: str | None = None
    support_email: str | None = None
