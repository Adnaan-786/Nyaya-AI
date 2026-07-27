from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDMixin


class Device(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "devices"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
    )

    fcm_token: Mapped[str] = mapped_column(String)

    platform: Mapped[str] = mapped_column(String(30))

    app_version: Mapped[str] = mapped_column(String(30))

    user = relationship(
        "User",
        back_populates="devices",
    )