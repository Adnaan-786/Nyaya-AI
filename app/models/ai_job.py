import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.enums import AIJobStatus
from app.db.mixins import TenantMixin, TimestampMixin, UUIDMixin


class AIJob(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "ai_jobs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    status: Mapped[AIJobStatus] = mapped_column(
        nullable=False,
        default=AIJobStatus.PENDING,
    )

    input: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    result: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    tenant = relationship("Tenant", back_populates="ai_jobs")
    user = relationship("User", back_populates="ai_jobs")