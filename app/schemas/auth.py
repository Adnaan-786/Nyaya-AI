from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.user import UserOut


class OTPRequestIn(BaseModel):
    phone: str = Field(..., pattern=r"^\+[1-9]\d{7,14}$", examples=["+919812345678"])


class OTPVerifyIn(BaseModel):
    phone: str = Field(..., pattern=r"^\+[1-9]\d{7,14}$")
    otp: str = Field(..., min_length=4, max_length=8, pattern=r"^\d+$")


class RefreshIn(BaseModel):
    refresh_token: str


class OnboardIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    role_hint: Literal["lawyer", "firm_admin"]
    firm_name: str | None = Field(default=None, max_length=255)
    bar_council_id: str | None = Field(default=None, max_length=50)
    language: str = Field(default="en", pattern="^(en|hi)$")


class TokenPairOut(BaseModel):
    access_token: str
    refresh_token: str
    is_new_user: bool
    user: UserOut


class TokenRefreshOut(BaseModel):
    access_token: str
    refresh_token: str
