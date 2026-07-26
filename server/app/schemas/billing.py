"""Invoicing, time tracking and payments (B.5, B.6, B.10).

Every money field is **integer paise**, named `*_paise` so a `float` can never
sneak in unnoticed. Rs. 1,500.50 is 150050.
"""

import datetime as dt
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field

# Legal services in India are taxed at 18% when GST applies at all.
DEFAULT_GST_RATE = 18


class LineItem(BaseModel):
    description: str = Field(min_length=1, max_length=300)
    quantity: int = Field(default=1, ge=1)
    rate_paise: int = Field(ge=0)

    @computed_field
    @property
    def amount_paise(self) -> int:
        return self.quantity * self.rate_paise


class InvoiceCreate(BaseModel):
    client_id: uuid.UUID
    case_id: uuid.UUID | None = None
    line_items: list[LineItem] = Field(min_length=1)
    gst_rate: int = Field(default=DEFAULT_GST_RATE, ge=0, le=28)
    due_date: dt.date | None = None
    # Import unbilled time for this case as line items (D.9 "Import unbilled time").
    import_unbilled_time: bool = False
    reverse_charge: bool = Field(
        default=False,
        description=(
            "Legal services supplied by an advocate to a business entity fall under "
            "the GST reverse charge mechanism: the recipient pays the GST, and the "
            "advocate's invoice carries none. Setting this zeroes the tax on the "
            "invoice and prints the statutory note."
        ),
    )


class InvoiceUpdate(BaseModel):
    line_items: list[LineItem] | None = None
    gst_rate: int | None = Field(default=None, ge=0, le=28)
    due_date: dt.date | None = None
    status: Literal["draft", "sent", "paid", "overdue"] | None = None


class InvoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    client_id: uuid.UUID
    case_id: uuid.UUID | None = None
    number: str
    line_items: list[dict]
    subtotal_paise: int
    gst_rate: int
    gst_paise: int
    total_paise: int
    status: str
    due_date: dt.date | None = None
    pdf_url: str | None = None
    payment_link: str | None = None
    created_at: dt.datetime


class TimeEntryCreate(BaseModel):
    case_id: uuid.UUID
    started_at: dt.datetime
    duration_seconds: int = Field(ge=0)
    description: str | None = None
    billable: bool = True
    rate_paise: int | None = Field(default=None, ge=0)


class TimeEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    case_id: uuid.UUID
    user_id: uuid.UUID
    started_at: dt.datetime
    duration_seconds: int
    description: str | None = None
    billable: bool
    rate_paise: int | None = None
    invoiced_at: dt.datetime | None = None


class ExpenseCreate(BaseModel):
    case_id: uuid.UUID | None = None
    description: str = Field(min_length=1, max_length=300)
    amount_paise: int = Field(ge=0)
    category: str | None = None
    incurred_on: dt.date | None = None
    receipt_document_id: uuid.UUID | None = None


class ExpenseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    case_id: uuid.UUID | None = None
    description: str
    amount_paise: int
    category: str | None = None
    incurred_on: dt.date | None = None
    created_at: dt.datetime


class PaymentOrderRequest(BaseModel):
    invoice_id: uuid.UUID


class PaymentOrderOut(BaseModel):
    """B.10 step 2 — exactly what the Razorpay Checkout SDK needs."""

    razorpay_order_id: str
    amount_paise: int
    key_id: str


class PaymentVerifyRequest(BaseModel):
    """B.10 step 4. The app sends what the SDK handed it; the server decides."""

    order_id: str
    payment_id: str
    signature: str


class PaymentVerifyOut(BaseModel):
    # Deliberately returns the *invoice* status, not a payment boolean: B.10 says
    # the app treats the server's invoice status as truth, never its own SDK result.
    invoice_id: uuid.UUID
    invoice_status: str
    verified: bool
