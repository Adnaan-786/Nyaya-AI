from datetime import time

from sqlalchemy import Boolean, ForeignKey, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDMixin


class NotificationSettings(Base, UUIDMixin, TimestampMixin):
    """
    One row per user. Not tenant-scoped via RLS (same as Device,
    RefreshToken) since it's strictly owned by a single user regardless
    of tenant, and every access path already filters by user_id.
    """

    __tablename__ = "notification_settings"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Plan C.10: "daily digest at user-configured time (default 19:00)".
    digest_time: Mapped[time] = mapped_column(
        Time,
        nullable=False,
        default=time(19, 0),
    )

    push_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    whatsapp_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sms_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    user = relationship("User", back_populates="notification_settings")
