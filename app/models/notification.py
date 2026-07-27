from sqlalchemy import ForeignKey, JSON, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from datetime import datetime
from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDMixin
from app.db.enums import NotificationType


class Notification(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "notifications"

    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )

    type: Mapped[NotificationType] = mapped_column(
        String(50),
    )

    payload: Mapped[dict] = mapped_column(
        JSON,
    )

    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    tenant = relationship(
        "Tenant",
        back_populates="notifications",
    )

    user = relationship(
        "User",
        back_populates="notifications",
    )