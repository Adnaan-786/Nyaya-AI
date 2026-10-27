from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LineItemIn(BaseModel):
    description: str = Field(..., min_length=1, max_length=500)
    qty: float = Field(..., gt=0)
    rate_paise: int = Field(..., ge=0)


class LineItemOut(BaseModel):
    description: str
    qty: float
    rate_paise: int
    amount_paise: int


class InvoiceCreateIn(BaseModel):
    client_id: UUID
    case_id: UUID | None = None
    line_items: list[LineItemIn] = Field(..., min_length=1)
    gst_rate: int | None = None
    due_date: date | None = None


class InvoiceFromTimeEntriesIn(BaseModel):
    client_id: UUID
    case_id: UUID
    gst_rate: int | None = None
    due_date: date | None = None


class InvoiceUpdateIn(BaseModel):
    line_items: list[LineItemIn] | None = None
    due_date: date | None = None


class InvoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    number: str
    client_id: UUID
    case_id: UUID | None = None
    line_items: list[LineItemOut]
    subtotal_paise: int
    gst_rate: int
    gst_paise: int
    total_paise: int
    status: str
    due_date: date | None = None
    razorpay_link: str | None = None
    created_at: datetime
