from datetime import date

from sqlalchemy import Boolean, Date, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.enums import PlanType
from app.db.mixins import TenantMixin, TimestampMixin, UUIDMixin


class Subscription(Base, UUIDMixin, TenantMixin, TimestampMixin):
    """
    One row per tenant: the billing system-of-record for cycle, mandate
    and renewal state. The tenant's *effective* plan for quota purposes
    is `Tenant.plan`, kept in sync by the activation webhook and the
    cycle-end downgrade job.
    """

    __tablename__ = "subscriptions"

    plan: Mapped[PlanType] = mapped_column(String(50), nullable=False, default=PlanType.FREE)
    cycle: Mapped[str] = mapped_column(String(20), nullable=False, default="monthly")
    # pending_activation | active | past_due | cancelled
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending_activation")
    razorpay_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    current_period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    tenant = relationship("Tenant", back_populates="subscription")
