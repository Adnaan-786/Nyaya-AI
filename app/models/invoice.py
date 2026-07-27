from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.enums import InvoiceStatus
from app.db.base import Base
from app.db.mixins import TimestampMixin, TenantMixin, UUIDMixin


class Invoice(Base, UUIDMixin, TenantMixin, TimestampMixin):
    __tablename__ = "invoices"

    number: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
    )

    client_id: Mapped[str] = mapped_column(
        ForeignKey("clients.id"),
        nullable=False,
    )

    case_id: Mapped[str | None] = mapped_column(
        ForeignKey("cases.id"),
        nullable=True,
    )

    line_items: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    subtotal_paise: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    gst_rate: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=18,
    )

    gst_paise: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    total_paise: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    status: Mapped[InvoiceStatus] = mapped_column(
        String(50),
        nullable=False,
        default=InvoiceStatus.DRAFT,
    )

    due_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    s3_pdf_key: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    razorpay_link: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    client = relationship(
        "Client",
        back_populates="invoices",
    )

    case = relationship(
        "Case",
        back_populates="invoices",
    )

    payments = relationship(
        "Payment",
        back_populates="invoice",
        cascade="all, delete-orphan",
    )

    tenant = relationship(
        "Tenant",
        back_populates="invoices",
    )