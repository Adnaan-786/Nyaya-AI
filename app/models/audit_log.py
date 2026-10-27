from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import UUIDMixin


class AuditLog(Base, UUIDMixin):
    __tablename__ = "audit_logs"
    # Monthly range partitions on `at` (plan C.12.1). Postgres requires
    # the partition key to be part of the primary key, hence (id, at).
    # Partitions are created by the `audit_create_partition()` SQL
    # function (see migration c3d4e5f6a7b8) and a scheduled job.
    __table_args__ = {"postgresql_partition_by": "RANGE (at)"}

    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )

    actor_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
    )

    action: Mapped[str] = mapped_column(String(100))

    entity_type: Mapped[str] = mapped_column(String(100))

    # NULL for actions with no single target (and for creates where the
    # new id isn't known to the middleware).
    entity_id: Mapped[str | None] = mapped_column(String, nullable=True)

    ip: Mapped[str | None] = mapped_column(String(50))

    user_agent: Mapped[str | None] = mapped_column(String)

    at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        primary_key=True,
        default=lambda: datetime.now(timezone.utc),
    )

    tenant = relationship(
        "Tenant",
        back_populates="audit_logs",
    )

    actor = relationship(
        "User",
        back_populates="audit_logs",
    )