from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ConsentTextOut(BaseModel):
    version: str
    language: str
    text: str
    text_hash: str


class ConsentIn(BaseModel):
    version: str
    language: Literal["en", "hi"] = "en"


class ConsentStatusOut(BaseModel):
    accepted: bool
    current_version: str


class DataRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    kind: str
    status: str
    scheduled_for: datetime | None = None
    completed_at: datetime | None = None
    expires_at: datetime | None = None
    summary: dict = {}
    download_url: str | None = None
    created_at: datetime


class LegalHoldIn(BaseModel):
    legal_hold: bool
