from datetime import date
from typing import Literal

from pydantic import BaseModel


class PlanOut(BaseModel):
    id: str
    name: str
    price_paise_monthly: int
    price_paise_yearly: int
    max_cases: int
    ai_jobs_per_day: int
    storage_gb: int


class SubscriptionOut(BaseModel):
    plan: str
    cycle: str
    status: str
    current_period_end: date | None = None
    cancel_at_period_end: bool
    usage: dict


class SubscriptionCheckoutIn(BaseModel):
    plan_id: str
    cycle: Literal["monthly", "yearly"]


class SubscriptionCheckoutOut(BaseModel):
    razorpay_subscription_id: str
    checkout_url: str
