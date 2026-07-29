from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.rls import set_tenant
from app.db.session import get_db
from app.db.tenant import TenantContext

_bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class AuthContext:
    """
    Everything derived from a validated access token.
    Superset of TenantContext (kept for backward-compatible repository use).
    """

    user_id: UUID
    tenant_id: UUID
    role: str

    def as_tenant_context(self) -> TenantContext:
        return TenantContext(tenant_id=self.tenant_id, user_id=self.user_id)


async def get_current_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> AuthContext:
    """
    Decodes and validates the `Authorization: Bearer <token>` header.
    This is the sole source of truth for "who is calling" -- the app
    must never trust client-supplied tenant/user IDs (contract B.4).
    """
    from app.core.exceptions import AuthenticationException

    if credentials is None or not credentials.credentials:
        raise AuthenticationException("Missing bearer token.")

    payload = decode_access_token(credentials.credentials)

    try:
        user_id = UUID(payload["sub"])
        tenant_id = UUID(payload["tenant_id"])
        role = payload["role"]
    except (KeyError, ValueError, TypeError) as exc:
        raise AuthenticationException("Malformed authentication token.") from exc

    return AuthContext(user_id=user_id, tenant_id=tenant_id, role=role)


async def get_tenant_context(
    auth: AuthContext = Depends(get_current_auth),
) -> TenantContext:
    """Back-compat shim: existing Repository-based code depends on this."""
    return auth.as_tenant_context()


async def get_tenant_scoped_db(
    session: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
) -> AsyncSession:
    """
    A DB session with the Postgres RLS session variable already set for
    the calling tenant. Use this (instead of get_db directly) in any
    route that reads/writes tenant-scoped tables.
    """
    await set_tenant(session, str(tenant.tenant_id))
    return session
