from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDMixin
from sqlalchemy import Enum
from app.db.enums import PlanType

class Tenant(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    plan: Mapped[PlanType] = mapped_column(
        Enum(PlanType),
        nullable=False,
        default=PlanType.FREE,
    )
    users = relationship(
        "User",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )

    clients = relationship(
        "Client",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )

    cases = relationship(
        "Case",
        back_populates= "tenant",
        cascade= "all, delete-orphan",
    )

    hearings = relationship(
        "Hearing",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )

    documents = relationship(
        "Document",
        back_populates="tenant",
        cascade = "all, delete-orphan",
    )

    ai_jobs = relationship(
        "AIJob",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )

    ai_conversations = relationship(
        "AIConversation",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )

    invoices = relationship(
        "Invoice",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )

    payments = relationship(
        "Payment",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )

    time_entries = relationship(
        "TimeEntry",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )

    expenses = relationship(
        "Expense",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )

    tasks = relationship(
        "Task",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )

    notifications = relationship(
        "Notification",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )

    audit_logs = relationship(
        "AuditLog",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )