import datetime
import uuid

from sqlalchemy import Date, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TenantMixin, TimestampMixin, UUIDMixin


class Expense(Base, UUIDMixin, TenantMixin, TimestampMixin):
    __tablename__ = "expenses"

    case_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cases.id", ondelete="SET NULL"),
        nullable=True,
    )

    amount_paise: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    category: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    expense_date: Mapped[datetime.date] = mapped_column(
        Date,
        nullable=False,
    )

    tenant = relationship("Tenant", back_populates="expenses")
    case = relationship("Case", back_populates="expenses")