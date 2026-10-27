from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TenantMixin, TimestampMixin, UUIDMixin


class DataRequest(Base, UUIDMixin, TenantMixin, TimestampMixin):
    """
    A DPDP data-principal request (plan C.12.2): either an `export` of
    the user's data or a `delete` request with a 30-day soft window.
    """

    __tablename__ = "data_requests"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # export | delete

    # pending | processing | completed | failed | cancelled | expired
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")

    # delete: when the soft window ends and the hard delete may run.
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # export: S3 key of the ZIP and when its download link stops working.
    result_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Counts only -- never personal data.
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
