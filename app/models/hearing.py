import datetime
import uuid

from sqlalchemy import Date, ForeignKey, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.enums import HearingSource
from app.db.mixins import TenantMixin, TimestampMixin, UUIDMixin


class Hearing(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "hearings"

    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    date: Mapped[datetime.date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )

    time: Mapped[datetime.time | None] = mapped_column(
        Time,
        nullable=True,
    )

    purpose: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    courtroom: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    outcome_notes: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    source: Mapped[HearingSource] = mapped_column(
        nullable=False,
        default=HearingSource.MANUAL,
    )

    tenant = relationship(
        "Tenant",
        back_populates="hearings",
    )

    case = relationship(
        "Case",
        back_populates="hearings",
    )