"""Async engine, session factory, and the tenant-scoping helper."""

from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import Select, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Import the package, not just the base module: this is what registers every
# table on the metadata before create_all / Alembic autogenerate runs.
import app.models  # noqa: F401
from app.core.config import get_settings
from app.models.base import Base

settings = get_settings()

engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
SessionFactory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionFactory() as session:
        yield session


async def create_all() -> None:
    """Used for local bring-up and tests; staging goes through Alembic."""
    async with engine.begin() as conn:
        # `pg_trgm` backs the trigram index on documents.ocr_text that universal search
        # uses. Creating it here rather than leaving it as a README step: a fresh cluster
        # otherwise fails on "operator class gin_trgm_ops does not exist" halfway through
        # table creation, which reads like a code bug rather than a missing extension.
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        await conn.run_sync(Base.metadata.create_all)


def scoped[ModelT](model: type[ModelT], tenant_id: Any) -> Select:
    """Every read of a tenant table must start here.

    Writing `select(Case)` directly is the bug that leaks firm A's cases to firm B.
    Making the scoped helper the only convenient path is the cheapest defence; the
    automated cross-tenant check in IC-4 is the proof.
    """
    return select(model).where(model.tenant_id == tenant_id)  # type: ignore[attr-defined]
