from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AuthContext, get_tenant_scoped_db
from app.core.exceptions import FirmNotFoundException
from app.core.rbac import require
from app.core.responses import ApiResponse
from app.models.tenant import Tenant

router = APIRouter(prefix="/firm", tags=["Firm"])


@router.get("", response_model=ApiResponse[dict])
async def get_firm(
    auth: AuthContext = Depends(require("firm.manage")),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[dict]:
    result = await session.execute(select(Tenant).where(Tenant.id == auth.tenant_id))
    tenant = result.scalar_one_or_none()

    if tenant is None:
        raise FirmNotFoundException()

    plan = tenant.plan.value if hasattr(tenant.plan, "value") else tenant.plan

    return ApiResponse(
        success=True,
        data={"id": str(tenant.id), "name": tenant.name, "plan": plan},
    )
