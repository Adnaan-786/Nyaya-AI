import uuid

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CaseAssignee(Base):
    __tablename__ = "case_assignees"

    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"),
        primary_key=True,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )

    case = relationship(
        "Case",
        back_populates="assignees",
    )

    user = relationship(
        "User",
        back_populates="assigned_cases",
    )

    tasks = relationship(
        "Task",
        back_populates="assignee",
        cascade="all, delete-orphan",
    )