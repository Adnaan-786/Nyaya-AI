from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FirmOut(BaseModel):
    id: UUID
    name: str
    plan: str


class FirmUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)


class MemberInviteIn(BaseModel):
    phone: str = Field(..., pattern=r"^\+[1-9]\d{7,14}$")
    name: str = Field(..., min_length=1, max_length=255)
    role: Literal["firm_admin", "lawyer", "intern"]


class MemberRoleChangeIn(BaseModel):
    role: Literal["firm_admin", "lawyer", "intern"]


class MemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    phone: str
    email: str | None = None
    role: str
    language: str
    created_at: datetime
