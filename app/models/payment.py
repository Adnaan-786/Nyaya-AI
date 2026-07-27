from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.enums import PaymentStatus
from app.db.base import Base
from app.db.mixins import TenantMixin, TimestampMixin, UUIDMixin


class Payment(Base, UUIDMixin, TenantMixin, TimestampMixin):
    __tablename__ = "payments"

    invoice_id: Mapped[str] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    razorpay_order_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    razorpay_payment_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    amount_paise: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    status: Mapped[PaymentStatus] = mapped_column(
        String(50),
        nullable=False,
        default=PaymentStatus.PENDING,
    )

    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    invoice = relationship(
        "Invoice",
        back_populates="payments",
    )

    tenant = relationship(
        "Tenant",
        back_populates="payments",
    )
