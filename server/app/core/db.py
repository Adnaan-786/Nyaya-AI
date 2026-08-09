"""Async engine, session factory, schema bring-up, and the tenant-scoping helper."""

import asyncio
import logging
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Select, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Import the package, not just the base module: this is what registers every table on
# the metadata. `migrations/env.py` imports it for the same reason, but importing it
# here too keeps `scoped()` and any ad-hoc session use working without depending on
# whether Alembic happened to run first.
import app.models  # noqa: F401
from app.core.config import get_settings
from app.models.base import Base

logger = logging.getLogger(__name__)
settings = get_settings()

_connect_args: dict = {"ssl": True} if settings.database_requires_ssl else {}
engine = create_async_engine(
    settings.database_url, echo=False, pool_pre_ping=True, connect_args=_connect_args,
)
SessionFactory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionFactory() as session:
        yield session


ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"

# The first migration, which reproduces the schema as it stood when this database was
# still being built by `create_all()` plus hand-written ALTERs. A database that predates
# migrations is stamped with *this* revision rather than `head`, so that anything added
# after the baseline still runs against it.
BASELINE_REVISION = "aff0fc9b19b9"


def _alembic_config() -> Config:
    config = Config(str(ALEMBIC_INI))
    # env.py reads the URL from app settings, so nothing needs setting here — but the
    # script location in alembic.ini is relative, and the process may be started from
    # anywhere (Render runs uvicorn from the repo's `server/` dir, pytest from wherever
    # the developer happens to be).
    config.set_main_option("script_location", str(ALEMBIC_INI.parent / "migrations"))
    # See migrations/env.py: without this the app's own logging setup is replaced by
    # alembic.ini's the first time a migration runs, and every log line after startup
    # loses the JSON format the deployment's log search depends on.
    config.attributes["configure_logger"] = False
    return config


def _run_alembic(action: str, revision: str) -> None:
    """Alembic's command API is synchronous and `migrations/env.py` calls `asyncio.run`.

    Both facts mean this cannot be awaited from the app's event loop — it has to happen
    on a thread with no loop of its own, which is what the callers below arrange.
    """
    config = _alembic_config()
    if action == "stamp":
        command.stamp(config, revision)
    else:
        command.upgrade(config, revision)


async def _predates_migrations() -> bool:
    """True for a database that has this app's tables but no Alembic history.

    That is exactly the deployed database as it stands today: every table on it was
    created by the old `create_all()` path, so running the baseline migration against it
    would fail on the first `CREATE TABLE`. It needs stamping, not running.
    """
    async with engine.connect() as conn:
        has_history = await conn.scalar(text("SELECT to_regclass('public.alembic_version')"))
        has_tables = await conn.scalar(text("SELECT to_regclass('public.users')"))
    return has_history is None and has_tables is not None


async def ensure_schema() -> None:
    """Bring the database to the latest migration, whatever state it starts in.

    Three cases, all of which have to work unattended because this runs at startup:

    - **Empty database** (a fresh clone, CI, a new Render instance): every migration
      runs, baseline first.
    - **Database that predates Alembic** (production, right now): stamped at the
      baseline so its existing tables are left untouched, then any later migration runs.
    - **Database already under Alembic**: the normal upgrade path, a no-op when it is
      already at head.
    """
    if await _predates_migrations():
        logger.info("database predates alembic; stamping baseline %s", BASELINE_REVISION)
        await asyncio.to_thread(_run_alembic, "stamp", BASELINE_REVISION)
        await _warn_on_drift()

    await asyncio.to_thread(_run_alembic, "upgrade", "head")
    logger.info("schema is at head")


def _drift(connection) -> list:
    context = MigrationContext.configure(connection, opts={"compare_type": True})
    return compare_metadata(context, Base.metadata)


async def _warn_on_drift() -> None:
    """Check, once, that a just-stamped database really does match the baseline.

    Stamping asserts "this database is already at that revision" without looking, so a
    database that quietly differs would be accepted here and only fail later, from
    inside some unrelated migration. This runs exactly once — on the transition from no
    Alembic history to stamped — and only logs: a difference is worth investigating but
    is not a reason to refuse to start, and the app served requests against this schema
    a moment ago.
    """
    async with engine.connect() as conn:
        differences = await conn.run_sync(_drift)

    if differences:
        logger.warning(
            "stamped database differs from the baseline in %d place(s); "
            "the next migration may not apply cleanly: %s",
            len(differences),
            differences,
        )
    else:
        logger.info("stamped database matches the baseline exactly")


def scoped[ModelT](model: type[ModelT], tenant_id: Any) -> Select:
    """Every read of a tenant table must start here.

    Writing `select(Case)` directly is the bug that leaks firm A's cases to firm B.
    Making the scoped helper the only convenient path is the cheapest defence; the
    automated cross-tenant check in IC-4 is the proof.
    """
    return select(model).where(model.tenant_id == tenant_id)  # type: ignore[attr-defined]
