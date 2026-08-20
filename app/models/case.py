import datetime
import uuid

from sqlalchemy import Boolean, Date, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.enums import CaseStatus
from app.db.mixins import TenantMixin, TimestampMixin, UUIDMixin


class Case(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "cases"

    cnr: Mapped[str | None] = mapped_column(
        String(32),
        unique=True,
        nullable=True,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    case_number: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    court_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    court_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    judge_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    case_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    stage: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    status: Mapped[CaseStatus] = mapped_column(
        nullable=False,
        default=CaseStatus.OPEN,
    )

    client_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    next_hearing_date: Mapped[datetime.date | None] = mapped_column(
        Date,
        nullable=True,
        index=True,
    )

    ecourts_synced: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    last_synced_at: Mapped[datetime.datetime | None]

    sync_failure_count: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )

    consecutive_sync_failures: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )

    last_sync_error: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    raw_ecourts: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    tenant = relationship(
        "Tenant",
        back_populates="cases",
    )

    client = relationship(
        "Client",
        back_populates="cases",
    )

    hearings = relationship(
        "Hearing",
        back_populates="case",
        cascade="all, delete-orphan",
    )

    documents = relationship(
        "Document",
        back_populates="case",
        cascade="all, delete-orphan",
    )

    assignees = relationship(
        "CaseAssignee",
        back_populates="case",
        cascade="all, delete-orphan",
    )

    invoices = relationship(
        "Invoice",
        back_populates="case",
    )

    time_entries = relationship(
        "TimeEntry",
        back_populates="case",
        cascade="all, delete-orphan",
    )

    expenses = relationship(
        "Expense",
        back_populates="case",
        cascade="all, delete-orphan",
    )

    tasks = relationship(
        "Task",
        back_populates="case",
        cascade="all, delete-orphan",
    )

    notes = relationship(
        "CaseNote",
        back_populates="case",
        cascade="all, delete-orphan",
    )