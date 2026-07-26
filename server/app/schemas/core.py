"""Client, case, hearing and calendar schemas (B.5 / B.6).

Note the deliberate split of temporal types, which the Android client mirrors exactly:

* `dt.datetime` for genuine moments — `created_at`, `last_synced_at`.
* `dt.date` for calendar days — `next_hearing_date`, `hearing.date`, `due_date`.

FastAPI emits these as `format: date-time` and `format: date` respectively, so the
generated OpenAPI carries the distinction and any future codegen gets it right for free.

The import is qualified (`import datetime as dt`) because fields genuinely named `date`
and `time` would otherwise shadow the same-named types for every annotation that follows
them inside the class body.
"""

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator

CNR_LENGTH = 16


class ClientCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    phone: str = Field(min_length=10, max_length=20)
    email: str | None = None
    address: str | None = None
    notes: str | None = None
    tags: list[str] = []


class ClientUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    notes: str | None = None
    tags: list[str] | None = None


class ClientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    phone: str
    email: str | None = None
    address: str | None = None
    notes: str | None = None
    tags: list[str] = []
    created_at: dt.datetime


class CaseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=400)
    client_id: uuid.UUID | None = None
    cnr: str | None = None
    case_number: str | None = None
    court_name: str | None = None
    court_type: str | None = None
    judge_name: str | None = None
    case_type: str | None = None
    stage: str | None = None
    next_hearing_date: dt.date | None = None


class CaseUpdate(BaseModel):
    title: str | None = None
    client_id: uuid.UUID | None = None
    court_name: str | None = None
    judge_name: str | None = None
    stage: str | None = None
    status: str | None = Field(default=None, pattern="^(active|disposed|archived)$")
    next_hearing_date: dt.date | None = None


class CaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    cnr: str | None = None
    title: str
    case_number: str | None = None
    court_name: str | None = None
    court_type: str | None = None
    judge_name: str | None = None
    case_type: str | None = None
    stage: str | None = None
    status: str
    client_id: uuid.UUID | None = None
    assigned_user_ids: list[uuid.UUID] = []
    next_hearing_date: dt.date | None = None
    ecourts_synced: bool
    last_synced_at: dt.datetime | None = None
    created_at: dt.datetime


class CnrLookupRequest(BaseModel):
    cnr: str

    @field_validator("cnr")
    @classmethod
    def check_length(cls, value: str) -> str:
        cleaned = value.strip().upper().replace(" ", "")
        if len(cleaned) != CNR_LENGTH:
            # Surfaces as 422 CNR_INVALID, which the add-by-CNR field shows inline.
            raise ValueError("CNR must be 16 characters.")
        return cleaned


class HearingCreate(BaseModel):
    date: dt.date
    time: dt.time | None = None
    purpose: str | None = None
    courtroom: str | None = None


class HearingUpdate(BaseModel):
    date: dt.date | None = None
    time: dt.time | None = None
    purpose: str | None = None
    courtroom: str | None = None
    outcome_notes: str | None = None


class HearingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    case_id: uuid.UUID
    date: dt.date
    time: dt.time | None = None
    purpose: str | None = None
    courtroom: str | None = None
    outcome_notes: str | None = None
    source: str


class CnrPreviewOut(BaseModel):
    """What eCourts returned, before the user commits to creating the case."""

    cnr: str
    title: str
    case_number: str | None = None
    court_name: str | None = None
    court_type: str | None = None
    judge_name: str | None = None
    case_type: str | None = None
    stage: str | None = None
    parties: list[str] = []
    next_hearing_date: dt.date | None = None
    hearing_history: list[HearingOut] = []


class CaseFromCnrRequest(BaseModel):
    cnr: str
    client_id: uuid.UUID | None = None


class NoteCreate(BaseModel):
    body: str = Field(min_length=1)


class TimelineEvent(BaseModel):
    """B.6: merged hearings, documents, notes and status changes for a case."""

    kind: str
    at: dt.datetime
    title: str
    detail: str | None = None
    ref_id: uuid.UUID | None = None


class CalendarDay(BaseModel):
    date: dt.date
    hearings: list[HearingOut] = []


class TodayOut(BaseModel):
    date: dt.date
    hearings: list[HearingOut] = []
    tomorrow_count: int = 0
    unread_notifications: int = 0
    # Hearings whose date has passed with no outcome recorded — the "Kal ki hearing ka
    # outcome update karein" nudge on the Today screen (D.6).
    overdue_outcomes: list[HearingOut] = []
