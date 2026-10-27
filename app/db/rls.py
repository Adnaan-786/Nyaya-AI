"""
Row-Level Security context helpers.

The tenant id is stored on the SQLAlchemy session (`session.info`) and
re-applied as a *transaction-local* Postgres setting at the start of
every transaction (`after_begin`). Two properties matter:

  * It survives `commit()`: services commit several times per request,
    and each new transaction re-applies the context automatically.
  * It can never leak across requests: `set_config(..., is_local=true)`
    is discarded when the transaction ends, so a pooled connection is
    always handed back clean. (The previous session-level setting
    persisted after a commit and was inherited by the next request that
    happened to get the same pooled connection.)

Policies (see migration `b1f0c2d3e4a5`) treat a missing tenant as
"no rows" and honour a separate system-context flag for the few
pre-authentication lookups (OTP login, refresh) that legitimately have
no tenant yet.
"""

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

TENANT_KEY = "rls_tenant_id"
SYSTEM_KEY = "rls_system_context"


@event.listens_for(Session, "after_begin")
def _apply_rls_context(session, transaction, connection) -> None:
    tenant_id = session.info.get(TENANT_KEY)
    if tenant_id:
        connection.execute(
            text("SELECT set_config('app.tenant_id', :t, true)"), {"t": tenant_id}
        )
    if session.info.get(SYSTEM_KEY):
        connection.execute(text("SELECT set_config('app.bypass_rls', 'on', true)"))


async def set_tenant(session: AsyncSession, tenant_id: str) -> None:
    """Scopes this session (every current and future transaction) to one tenant."""
    session.sync_session.info[TENANT_KEY] = str(tenant_id)
    await session.execute(
        text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_id)}
    )


async def set_system_context(session: AsyncSession) -> None:
    """
    Cross-tenant system context, for the handful of lookups that happen
    before a tenant is known (phone -> user at OTP verify, refresh).
    Never use this from request handlers that already have a tenant.
    """
    session.sync_session.info[SYSTEM_KEY] = True
    await session.execute(text("SELECT set_config('app.bypass_rls', 'on', true)"))
