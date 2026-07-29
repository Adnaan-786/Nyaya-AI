from datetime import datetime

from sqlalchemy import DateTime, Integer, String

from sqlalchemy.orm import mapped_column, Mapped
from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDMixin


class OTPRequest(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "otp_requests"

    phone: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
    )

    code_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    attempts: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    send_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    window_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )