from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    name: str
    phone: str
    email: str | None = None
    role: str
    language: str
    bar_council_id: str | None = None
    created_at: datetime


class MeUpdateIn(BaseModel):
    """PATCH /me"""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    email: str | None = None
    language: str | None = Field(default=None, pattern="^(en|hi)$")
