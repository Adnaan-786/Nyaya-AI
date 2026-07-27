from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import UUIDMixin


class AuditLog(Base, UUIDMixin):
    __tablename__ = "audit_logs"

    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )

    actor_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
    )

    action: Mapped[str] = mapped_column(String(100))

    entity_type: Mapped[str] = mapped_column(String(100))

    entity_id: Mapped[str] = mapped_column(String)

    ip: Mapped[str | None] = mapped_column(String(50))

    user_agent: Mapped[str | None] = mapped_column(String)

    at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
    )

    tenant = relationship(
        "Tenant",
        back_populates="audit_logs",
    )

    actor = relationship(
        "User",
        back_populates="audit_logs",
    )