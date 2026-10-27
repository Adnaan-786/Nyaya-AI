from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDMixin

# Fixed singleton row id, so get-or-create never races into duplicates.
SINGLETON_ID = "00000000-0000-0000-0000-000000000001"


class AppConfig(Base, UUIDMixin, TimestampMixin):
    """Single-row, global (not tenant-scoped) config the app reads on cold start (contract B.14)."""

    __tablename__ = "app_config"

    min_supported_version: Mapped[str] = mapped_column(String(20), default="1.0.0")
    latest_version: Mapped[str] = mapped_column(String(20), default="1.0.0")
    feature_flags: Mapped[dict] = mapped_column(JSON, default=dict)
    status_banner: Mapped[str | None] = mapped_column(Text, nullable=True)
    support_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    support_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
