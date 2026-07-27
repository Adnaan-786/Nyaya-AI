from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TenantMixin, TimestampMixin, UUIDMixin


class Client(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "clients"

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    phone: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    address: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    tags: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    tenant = relationship(
        "Tenant",
        back_populates= "clients",
    )
    cases = relationship(
        "Case",
        back_populates="client",
        cascade="all, delete-orphan",
    )
    documents = relationship(
        "Document",
        back_populates="client",
    )
    invoices = relationship(
        "Invoice",
        back_populates="client",
    )