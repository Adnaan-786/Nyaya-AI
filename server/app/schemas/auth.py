"""Auth request/response schemas.

Field names are snake_case on the wire, matching what the Android DTOs decode with
their snake_case naming strategy. FastAPI generates the OpenAPI document from these,
so these classes *are* the contract now that both sides are ours.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OtpRequest(BaseModel):
    phone: str = Field(examples=["+919812345678"])

    @field_validator("phone")
    @classmethod
    def normalise(cls, value: str) -> str:
        digits = "".join(ch for ch in value if ch.isdigit())
        # Indian mobiles are 10 digits; accept with or without the country code and
        # store one canonical form so OTP lookup cannot miss on formatting.
        if len(digits) == 10:
            return f"+91{digits}"
        if len(digits) == 12 and digits.startswith("91"):
            return f"+{digits}"
        raise ValueError("Enter a 10-digit Indian mobile number.")


class OtpVerifyRequest(OtpRequest):
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
    phone: str
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
