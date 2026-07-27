import uuid

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TenantMixin, TimestampMixin, UUIDMixin


class AIConversation(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "ai_conversations"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    messages: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )

    tenant = relationship(
        "Tenant",
        back_populates="ai_conversations",
    )

    user = relationship(
        "User",
        back_populates="ai_conversations",
    )