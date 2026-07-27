from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDMixin


class Consent(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "consents"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
    )

    version: Mapped[str] = mapped_column(String(30))

    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
    )

    text_hash: Mapped[str] = mapped_column(String(255))

    user = relationship(
        "User",
        back_populates="consents",
    )