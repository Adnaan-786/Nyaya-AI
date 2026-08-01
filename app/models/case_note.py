import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TenantMixin, TimestampMixin, UUIDMixin


class CaseNote(Base, UUIDMixin, TenantMixin, TimestampMixin):
    __tablename__ = "case_notes"

    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    author_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    text: Mapped[str] = mapped_column(Text, nullable=False)

    tenant = relationship("Tenant")
    case = relationship("Case", back_populates="notes")
    author = relationship("User")
