from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DocumentUploadUrlIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    mime_type: str
    size_bytes: int = Field(..., gt=0)
    case_id: UUID | None = None
    client_id: UUID | None = None
    folder: str | None = Field(default=None, max_length=255)


class DocumentUploadUrlOut(BaseModel):
    upload_url: str
    document_id: UUID


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID | None = None
    client_id: UUID | None = None
    name: str
    folder: str | None = None
    mime_type: str
    size_bytes: int
    ocr_status: str
    ocr_error: str | None = None
    uploaded_by: UUID | None = None
    created_at: datetime
    download_url: str | None = None
