from uuid import UUID

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import utcnow
from app.models.audit_log import AuditLog


async def write_audit(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    actor_id: UUID | None,
    action: str,
    entity_type: str,
    entity_id: str,
    request: Request | None = None,
) -> None:
    """
    Writes a single audit row. Called explicitly from mutating routes
    (create/update/delete). The table is INSERT-only at the DB grant
    level (enforced properly in M11); this helper is the only writer.
    """

    ip = request.client.host if request and request.client else None
    user_agent = request.headers.get("user-agent") if request else None

    session.add(
        AuditLog(
            tenant_id=tenant_id,
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            ip=ip,
            user_agent=user_agent,
            at=utcnow(),
        )
    )
    # Caller is responsible for the surrounding commit (so the audit
    # row lands in the same transaction as the mutation it describes).
