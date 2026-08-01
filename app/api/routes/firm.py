from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AuthContext, get_tenant_scoped_db
from app.core.rbac import require
from app.core.responses import ApiResponse
from app.schemas.firm import (
    FirmOut,
    FirmUpdateIn,
    MemberInviteIn,
    MemberOut,
    MemberRoleChangeIn,
)
from app.services import firm_service

router = APIRouter(prefix="/firm", tags=["Firm"])


def _firm_out(firm) -> dict:
    plan = firm.plan.value if hasattr(firm.plan, "value") else firm.plan
    return {"id": str(firm.id), "name": firm.name, "plan": plan}


@router.get("", response_model=ApiResponse[dict])
async def get_firm(
    auth: AuthContext = Depends(require("firm.manage")),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[dict]:
    tenant = auth.as_tenant_context()
    firm = await firm_service.get_firm(session, tenant)
    return ApiResponse(success=True, data=_firm_out(firm))


@router.patch("", response_model=ApiResponse[dict])
async def update_firm(
    payload: FirmUpdateIn,
    auth: AuthContext = Depends(require("firm.manage")),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[dict]:
    tenant = auth.as_tenant_context()
    firm = await firm_service.get_firm(session, tenant)
    firm = await firm_service.update_firm(session, firm, name=payload.name)
    return ApiResponse(success=True, data=_firm_out(firm))


@router.get("/members", response_model=ApiResponse[list[MemberOut]])
async def list_members(
    auth: AuthContext = Depends(require("firm.members.manage")),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[list[MemberOut]]:
    tenant = auth.as_tenant_context()
    members = await firm_service.list_members(session, tenant)
    return ApiResponse(success=True, data=[MemberOut.model_validate(m) for m in members])


@router.post("/members/invite", response_model=ApiResponse[MemberOut])
async def invite_member(
    payload: MemberInviteIn,
    auth: AuthContext = Depends(require("firm.members.manage")),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[MemberOut]:
    tenant = auth.as_tenant_context()
    member = await firm_service.invite_member(
        session, tenant, phone=payload.phone, name=payload.name, role=payload.role
    )
    return ApiResponse(success=True, data=MemberOut.model_validate(member))


@router.patch("/members/{member_id}", response_model=ApiResponse[MemberOut])
async def change_member_role(
    member_id: UUID,
    payload: MemberRoleChangeIn,
    auth: AuthContext = Depends(require("firm.members.manage")),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[MemberOut]:
    tenant = auth.as_tenant_context()
    member = await firm_service.get_member_or_404(session, tenant, member_id)
    member = await firm_service.change_member_role(session, member, role=payload.role)
    return ApiResponse(success=True, data=MemberOut.model_validate(member))


@router.delete("/members/{member_id}", response_model=ApiResponse[dict])
async def remove_member(
    member_id: UUID,
    auth: AuthContext = Depends(require("firm.members.manage")),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[dict]:
    tenant = auth.as_tenant_context()
    member = await firm_service.get_member_or_404(session, tenant, member_id)
    await firm_service.remove_member(session, member)
    return ApiResponse(success=True, data={"removed": True})
