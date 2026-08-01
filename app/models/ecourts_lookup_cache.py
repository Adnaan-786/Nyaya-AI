from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import UUIDMixin


class ECourtsLookupCache(Base, UUIDMixin):
    """
    Caches the normalized preview returned by POST /cases/lookup-cnr
    for 24h (contract B.6). Not tenant-scoped: court data returned by
    a CNR lookup is public and identical regardless of which firm asks.
    """

    __tablename__ = "ecourts_lookup_cache"

    cnr: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)

    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)

    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
