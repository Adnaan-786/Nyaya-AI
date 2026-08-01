import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CaseCreateIn(BaseModel):
    """Manual case creation (CNR/eCourts-based creation is module M5)."""

    title: str = Field(..., min_length=1, max_length=255)
    client_id: UUID
    case_number: str | None = Field(default=None, max_length=100)
    court_name: str | None = Field(default=None, max_length=255)
    court_type: str | None = Field(default=None, max_length=100)
    judge_name: str | None = Field(default=None, max_length=255)
    case_type: str | None = Field(default=None, max_length=100)
    stage: str | None = Field(default=None, max_length=100)
    next_hearing_date: datetime.date | None = None
    assigned_user_ids: list[UUID] = Field(default_factory=list)


class CaseUpdateIn(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    case_number: str | None = None
    court_name: str | None = None
    court_type: str | None = None
    judge_name: str | None = None
    case_type: str | None = None
    stage: str | None = None
    status: Literal["open", "closed", "archived"] | None = None
    next_hearing_date: datetime.date | None = None


class CaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    cnr: str | None = None
    title: str
    case_number: str | None = None
    court_name: str | None = None
    court_type: str | None = None
    judge_name: str | None = None
    case_type: str | None = None
    stage: str | None = None
    status: str
    client_id: UUID
    next_hearing_date: datetime.date | None = None
    ecourts_synced: bool
    last_synced_at: datetime.datetime | None = None
    created_at: datetime.datetime


class HearingCreateIn(BaseModel):
    date: datetime.date
    time: datetime.time | None = None
    purpose: str | None = Field(default=None, max_length=255)
    courtroom: str | None = Field(default=None, max_length=255)


class HearingUpdateIn(BaseModel):
    date: datetime.date | None = None
    time: datetime.time | None = None
    purpose: str | None = None
    courtroom: str | None = None
    outcome_notes: str | None = None


class HearingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    date: datetime.date
    time: datetime.time | None = None
    purpose: str | None = None
    courtroom: str | None = None
    outcome_notes: str | None = None
    source: str


class CaseNoteCreateIn(BaseModel):
    text: str = Field(..., min_length=1)


class CaseNoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    author_id: UUID | None = None
    text: str
    created_at: datetime.datetime


class TimelineEventOut(BaseModel):
    type: Literal["hearing", "note"]
    at: datetime.datetime
    data: dict


class CNRLookupIn(BaseModel):
    cnr: str = Field(..., min_length=16, max_length=16)


class CaseFromCNRIn(BaseModel):
    cnr: str = Field(..., min_length=16, max_length=16)
    client_id: UUID


class CNRHearingHistoryOut(BaseModel):
    date: datetime.date
    purpose: str | None = None
    outcome_notes: str | None = None


class CNRLookupPreviewOut(BaseModel):
    """Normalized preview returned by POST /cases/lookup-cnr."""

    cnr: str
    title: str
    court_name: str | None = None
    court_type: str | None = None
    judge_name: str | None = None
    case_type: str | None = None
    stage: str | None = None
    parties: list[str] = Field(default_factory=list)
    next_hearing_date: datetime.date | None = None
    history: list[CNRHearingHistoryOut] = Field(default_factory=list)
