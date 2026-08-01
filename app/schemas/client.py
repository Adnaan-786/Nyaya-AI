from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ClientCreateIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    phone: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=255)
    address: str | None = None
    tags: list[str] = Field(default_factory=list)


class ClientUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    tags: list[str] | None = None


class ClientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    tags: list[str] = Field(default_factory=list)
    created_at: datetime
