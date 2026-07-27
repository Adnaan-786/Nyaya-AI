import datetime
import uuid

from sqlalchemy import Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.enums import TaskStatus
from app.db.mixins import TenantMixin, TimestampMixin, UUIDMixin


class Task(Base, UUIDMixin, TenantMixin, TimestampMixin):
    __tablename__ = "tasks"

    case_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cases.id", ondelete="SET NULL"),
        nullable=True,
    )

    assigned_to: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    due_date: Mapped[datetime.date | None] = mapped_column(
        Date,
        nullable=True,
    )

    status: Mapped[TaskStatus] = mapped_column(
        default=TaskStatus.PENDING,
        nullable=False,
    )

    tenant = relationship("Tenant", back_populates="tasks")
    case = relationship("Case", back_populates="tasks")
    assignee = relationship("User", back_populates="tasks")