from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.tenant import TenantContext
from app.models.audit_log import AuditLog


async def list_audit_logs(
    session: AsyncSession,
    tenant: TenantContext,
    *,
    actor_id: UUID | None = None,
    action: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[AuditLog], int]:
    conditions = [AuditLog.tenant_id == tenant.tenant_id]
    if actor_id:
        conditions.append(AuditLog.actor_id == actor_id)
    if action:
        conditions.append(AuditLog.action.ilike(f"%{action}%"))
    if entity_type:
        conditions.append(AuditLog.entity_type == entity_type)
    if entity_id:
        conditions.append(AuditLog.entity_id == entity_id)
    # `at` is the partition key: bounding it lets Postgres skip partitions.
    if date_from:
        conditions.append(AuditLog.at >= date_from)
    if date_to:
        conditions.append(AuditLog.at <= date_to)

    total = (await session.execute(select(func.count()).select_from(AuditLog).where(*conditions))).scalar_one()
    rows = await session.execute(
        select(AuditLog).where(*conditions).order_by(AuditLog.at.desc()).limit(limit).offset(offset)
    )
    return list(rows.scalars().all()), total
