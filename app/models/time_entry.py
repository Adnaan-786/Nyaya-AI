import datetime
import uuid

from sqlalchemy import Date, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TenantMixin, TimestampMixin, UUIDMixin


class TimeEntry(Base, UUIDMixin, TenantMixin, TimestampMixin):
    __tablename__ = "time_entries"

    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    date: Mapped[datetime.date] = mapped_column(
        Date,
        nullable=False,
    )

    duration_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    tenant = relationship("Tenant", back_populates="time_entries")
    case = relationship("Case", back_populates="time_entries")
    user = relationship("User", back_populates="time_entries")