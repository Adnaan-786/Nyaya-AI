"""Document and search schemas (B.9, B.6)."""

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict, Field


class UploadUrlRequest(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    mime_type: str
    size_bytes: int
    case_id: uuid.UUID | None = None
    client_id: uuid.UUID | None = None
    folder: str | None = None


class UploadUrlOut(BaseModel):
    """B.9 step 1. The app PUTs the bytes directly to `upload_url`, then confirms."""

    upload_url: str
    document_id: uuid.UUID
    expires_in_seconds: int


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    case_id: uuid.UUID | None = None
    client_id: uuid.UUID | None = None
    name: str
    folder: str | None = None
    mime_type: str
    size_bytes: int
    ocr_status: str
    # Short-lived (B.5). Regenerated on every read; never cached by the client.
    download_url: str | None = None
    uploaded_by: uuid.UUID | None = None
    created_at: dt.datetime


class SearchHit(BaseModel):
    id: uuid.UUID
    title: str
    subtitle: str | None = None
    # The matched fragment with the query in context, so the user can see *why* a
    # result matched rather than guessing.
    highlight: str | None = None


class SearchResults(BaseModel):
    """B.6: grouped results, not one flat list."""

    cases: list[SearchHit] = []
    clients: list[SearchHit] = []
    documents: list[SearchHit] = []
