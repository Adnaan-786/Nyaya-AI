from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

class UUIDMixin:
    """
    UUID primary key.
    """

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )


class TimestampMixin:
    """
    Automatically managed timestamps.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class TenantMixin:
    """
    Shared tenant_id column.
    """

    tenant_id: Mapped[uuid4] = mapped_column(
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )