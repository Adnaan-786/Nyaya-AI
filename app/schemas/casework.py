import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TaskCreateIn(BaseModel):
    case_id: UUID | None = None
    title: str = Field(..., min_length=1, max_length=255)
    assignee_id: UUID
    due_date: datetime.date | None = None
    description: str | None = None


class TaskUpdateIn(BaseModel):
    title: str | None = None
    due_date: datetime.date | None = None
    description: str | None = None
    status: Literal["open", "in_progress", "done"] | None = None


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID | None = None
    assigned_to: UUID
    title: str
    description: str | None = None
    due_date: datetime.date | None = None
    status: str


class TimeEntryCreateIn(BaseModel):
    case_id: UUID
    date: datetime.date
    duration_minutes: int = Field(..., gt=0)
    description: str | None = None


class TimeEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    user_id: UUID
    date: datetime.date
    duration_minutes: int
    description: str | None = None


class ExpenseCreateIn(BaseModel):
    case_id: UUID | None = None
    amount_paise: int = Field(..., gt=0)
    category: str = Field(..., min_length=1, max_length=100)
    expense_date: datetime.date
    description: str | None = None


class ExpenseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID | None = None
    amount_paise: int
    category: str
    expense_date: datetime.date
    description: str | None = None
