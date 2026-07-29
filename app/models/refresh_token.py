from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDMixin


class RefreshToken(Base, UUIDMixin, TimestampMixin):
    """
    Stores hashed refresh tokens for rotation + reuse detection.

    Each issued refresh token belongs to a "family" (family_id). On
    every successful refresh, the old token is marked revoked and a
    new token in the same family is issued. If a *revoked* token is
    ever presented again, it indicates the token was stolen/replayed,
    and the entire family is revoked (see app/services/auth_service.py).
    """

    __tablename__ = "refresh_tokens"

    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    family_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        default=uuid4,
        index=True,
    )

    token_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    user = relationship(
        "User",
        back_populates="refresh_tokens",
    )
