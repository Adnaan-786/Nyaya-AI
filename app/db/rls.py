from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

async def set_tenant(
    session: AsyncSession,
    tenant_id: str,
) -> None:
    """
    Sets the PostgreSQL session variable used by Row-Level Security.
    """

    await session.execute(
        text(
            "SELECT set_config('app.tenant_id', :tenant, false)"
        ),
        {"tenant": tenant_id},
    )