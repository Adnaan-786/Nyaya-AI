from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AuthContext, get_tenant_scoped_db
from app.core.rbac import require
from app.core.responses import ApiResponse, Meta
from app.schemas.audit import AuditLogOut
from app.services import audit_query_service

router = APIRouter(prefix="/audit", tags=["Audit"])


@router.get("", response_model=ApiResponse[list[AuditLogOut]])
async def list_audit_logs(
    actor_id: UUID | None = None,
    action: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    date_from: datetime | None = Query(default=None, alias="from"),
    date_to: datetime | None = Query(default=None, alias="to"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    auth: AuthContext = Depends(require("audit.read")),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[list[AuditLogOut]]:
    rows, total = await audit_query_service.list_audit_logs(
        session, auth.as_tenant_context(), actor_id=actor_id, action=action,
        entity_type=entity_type, entity_id=entity_id, date_from=date_from, date_to=date_to,
        limit=limit, offset=(page - 1) * limit,
    )
    return ApiResponse(
        success=True,
        data=[AuditLogOut.model_validate(r) for r in rows],
        meta=Meta(page=page, limit=limit, total=total),
    )
