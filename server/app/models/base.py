"""SQLAlchemy base and the tenancy mixin.

C.4: every business table carries `tenant_id UUID NOT NULL`. Isolation is enforced
twice in the plan — application layer and Postgres RLS. The repository layer below
is the application half and is mandatory on every query; RLS is the safety net and
is added as a migration once the schema settles.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    """B.1.5: every stored timestamp is timezone-aware UTC."""
    return datetime.now(UTC)


def new_id() -> uuid.UUID:
    return uuid.uuid4()


class Base(DeclarativeBase):
    pass


class UuidPk:
    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=new_id
    )


class Timestamped:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class TenantScoped:
    """Mixin for every table that holds firm data.

    A table without this is either global (plans) or a serious mistake — a missing
    tenant_id is how firm A ends up seeing firm B's cases, which is the automated
    cross-tenant test in IC-4.
    """

    @property
    def _tenant_fk(self) -> str:
        return "tenants.id"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )


class Tenant(UuidPk, Timestamped, Base):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    plan: Mapped[str] = mapped_column(String(50), default="solo", nullable=False)


Index("ix_tenants_name", Tenant.name)
