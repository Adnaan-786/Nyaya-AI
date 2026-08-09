"""Alembic environment.

Two things here are deliberate and worth knowing before editing:

**The URL comes from the app's own settings**, not `alembic.ini`. `Settings` already
normalises `postgres://` to `postgresql+asyncpg://` and strips the libpq-only query
params (`sslmode`, `channel_binding`) that asyncpg rejects — the exact handling that
makes Render's and Neon's connection strings work. Duplicating a URL in `alembic.ini`
would mean two parsers that have to agree forever, and a credential in a tracked file.

**The engine is async**, because the app's is. Alembic's `run_migrations` API is
synchronous, so the connection is driven through `run_sync` rather than Alembic being
handed an async connection it cannot use.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

# Importing the package is what registers every table on the metadata. Without it
# autogenerate sees an empty schema and cheerfully writes a migration that drops
# everything.
import app.models  # noqa: F401
from app.core.config import get_settings
from app.models.base import Base

config = context.config

# `fileConfig` reconfigures logging process-wide from the [loggers] section, which is
# what you want from the `alembic` CLI and emphatically not what you want when the app
# calls this at startup: it would replace main.py's JSON formatter with alembic.ini's
# plain one and silence every app logger for the rest of the process. `ensure_schema()`
# sets configure_logger=False for exactly that reason; the CLI leaves it unset.
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata

config.set_main_option("sqlalchemy.url", get_settings().database_url)


def _include_object(obj, name, type_, reflected, compare_to) -> bool:
    """Keeps Alembic's own bookkeeping table out of autogenerate diffs.

    Without this, `alembic check` on a migrated database reports `alembic_version` as a
    table the models do not define and proposes dropping it.
    """
    return not (type_ == "table" and name == "alembic_version")


def _configure(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=_include_object,
        # Without this a column changing from VARCHAR(20) to VARCHAR(255) — which this
        # schema has already done once, to otp_codes.phone — produces no diff at all.
        compare_type=True,
        compare_server_default=True,
        # Names every constraint deterministically, so a future autogenerate does not
        # emit spurious drop/create pairs for constraints Postgres auto-named.
        render_as_batch=False,
    )


def run_migrations_offline() -> None:
    """Emit SQL to stdout instead of running it — `alembic upgrade head --sql`.

    Useful for reviewing exactly what would touch production before it does.
    """
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=_include_object,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def _do_run(connection) -> None:
    _configure(connection)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(_do_run)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
