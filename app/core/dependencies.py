from uuid import UUID

from fastapi import Depends

from app.db.tenant import TenantContext


async def get_tenant_context() -> TenantContext:
    """
    Temporary implementation.

    Later this will decode the JWT.
    """

    return TenantContext(
        tenant_id=UUID("11111111-1111-1111-1111-111111111111"),
        user_id=UUID("22222222-2222-2222-2222-222222222222"),
    )