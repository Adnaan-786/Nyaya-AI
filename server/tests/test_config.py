"""Regression tests for Settings' DATABASE_URL normalisation.

The old `_normalise_database_url` blanket-stripped everything after `?`, so a
DSN that carries its target in the query string (the unix-socket default:
`postgresql://nyaya@/nyayaai?host=/tmp&port=5433`) silently lost its host/port
and asyncpg fell back to 127.0.0.1:5432 with no error. These tests pin the
fixed behavior: only libpq-only keys asyncpg rejects are dropped; host/port
survive all the way into the connect kwargs asyncpg receives.
"""

from sqlalchemy import make_url
from sqlalchemy.dialects.postgresql.asyncpg import PGDialect_asyncpg

from app.core.config import Settings


def _asyncpg_connect_opts(database_url: str) -> dict:
    """The kwargs asyncpg.connect() would receive, via SQLAlchemy's real dialect."""
    url = make_url(Settings(database_url=database_url).database_url)
    _, opts = PGDialect_asyncpg().create_connect_args(url)
    return opts


def test_sslmode_is_remembered_but_never_reaches_asyncpg():
    settings = Settings(
        database_url="postgresql://u:p@db.example.com:5433/nyayaai?sslmode=require"
    )
    assert settings.database_requires_ssl is True
    assert "sslmode" not in make_url(settings.database_url).query
    assert "sslmode" not in _asyncpg_connect_opts(
        "postgresql://u:p@db.example.com:5433/nyayaai?sslmode=require"
    )


def test_channel_binding_is_stripped_and_benign_params_survive():
    url = "postgresql://u:p@db.example.com/nyayaai?channel_binding=require&statement_cache_size=0"
    settings = Settings(database_url=url)
    assert settings.database_requires_ssl is False
    query = make_url(settings.database_url).query
    assert "channel_binding" not in query
    assert query["statement_cache_size"] == "0"


def test_query_param_host_and_port_resolve_instead_of_silent_localhost_fallback():
    # The shape of the shipped default DSN: authority has no host, target lives
    # in the query. Before the fix these were stripped and asyncpg dialled
    # 127.0.0.1:5432 instead of /tmp/.s.PGSQL.5433.
    opts = _asyncpg_connect_opts("postgresql+asyncpg://nyaya@/nyayaai?host=/tmp&port=5433")
    assert opts["host"] == "/tmp"
    assert opts["port"] == 5433


def test_query_param_host_and_port_coexist_with_stripped_sslmode():
    opts = _asyncpg_connect_opts(
        "postgresql://nyaya@/nyayaai?host=/tmp&port=5433&sslmode=require"
    )
    assert opts["host"] == "/tmp"
    assert opts["port"] == 5433
    assert "sslmode" not in opts


def test_postgres_scheme_still_upgrades_to_asyncpg():
    settings = Settings(database_url="postgres://u:p@db.example.com/nyayaai")
    assert settings.database_url.startswith("postgresql+asyncpg://")


def test_plain_ssl_query_key_still_triggers_requires_ssl():
    settings = Settings(database_url="postgresql://u@db.example.com/nyayaai?ssl=true")
    assert settings.database_requires_ssl is True
