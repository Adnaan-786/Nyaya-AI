from sqlalchemy import ForeignKey, String

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin
from app.db.mixins import UUIDMixin

class User(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "users"

    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    phone: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    email: Mapped[str | None] = mapped_column(
        String(255),
    )

    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    language: Mapped[str] = mapped_column(
        String(20),
        default="en",
    )

    tenant = relationship(
        "Tenant",
        back_populates= "users",
    )

    assigned_cases = relationship(
        "CaseAssignee",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    ai_jobs = relationship(
        "AIJob",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    ai_conversations = relationship(
        "AIConversation",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    time_entries = relationship(
        "TimeEntry",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    notifications = relationship(
        "Notification",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    devices = relationship(
        "Device",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    audit_logs = relationship(
        "AuditLog",
        back_populates="actor",
    )

    consents = relationship(
        "Consent",
        back_populates="user",
        cascade="all, delete-orphan",
    )