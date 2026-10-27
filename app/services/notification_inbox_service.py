from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import utcnow
from app.db.tenant import TenantContext
from app.models.notification import Notification


async def list_notifications(
    session: AsyncSession,
    tenant: TenantContext,
    user_id: UUID,
    *,
    unread_only: bool = False,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Notification], int]:
    stmt = (
        select(Notification)
        .where(Notification.tenant_id == tenant.tenant_id)
        .where(Notification.user_id == user_id)
    )
    count_stmt = (
        select(Notification.id)
        .where(Notification.tenant_id == tenant.tenant_id)
        .where(Notification.user_id == user_id)
    )

    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
        count_stmt = count_stmt.where(Notification.read_at.is_(None))

    total = len((await session.execute(count_stmt)).all())

    stmt = stmt.order_by(Notification.created_at.desc()).limit(limit).offset(offset)
    result = await session.execute(stmt)

    return list(result.scalars().all()), total


async def mark_read(
    session: AsyncSession,
    tenant: TenantContext,
    user_id: UUID,
    *,
    ids: list[UUID] | None,
) -> int:
    """Marks the given notification ids (or every unread one, if ids is None) as read."""
    stmt = (
        update(Notification)
        .where(Notification.tenant_id == tenant.tenant_id)
        .where(Notification.user_id == user_id)
        .where(Notification.read_at.is_(None))
        .values(read_at=utcnow())
    )
    if ids:
        stmt = stmt.where(Notification.id.in_(ids))

    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount or 0
