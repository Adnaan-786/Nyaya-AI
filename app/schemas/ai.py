from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel


class SummarizeIn(BaseModel):
    document_id: UUID
    doc_type_hint: Literal["chargesheet", "judgment", "notice", "agreement", "other"] | None = None


class AIJobAcceptedOut(BaseModel):
    job_id: UUID
    status: Literal["queued"] = "queued"
    estimated_seconds: int


class AIJobOut(BaseModel):
    id: UUID
    type: str
    status: Literal["queued", "running", "done", "failed"]
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime
    completed_at: datetime | None = None

    @classmethod
    def from_model(cls, job) -> "AIJobOut":
        from app.services.ai_job_service import wire_status

        status = wire_status(job.status)
        return cls(
            id=job.id,
            type=job.type,
            status=status,
            result=job.result,
            error=job.error,
            created_at=job.created_at,
            completed_at=job.updated_at if status in ("done", "failed") else None,
        )
