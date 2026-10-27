from uuid import UUID

from pydantic import BaseModel


class PaymentOrderIn(BaseModel):
    invoice_id: UUID


class PaymentOrderOut(BaseModel):
    razorpay_order_id: str
    amount_paise: int
    key_id: str


class PaymentVerifyIn(BaseModel):
    order_id: str
    payment_id: str
    signature: str
