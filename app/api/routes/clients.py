from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AuthContext, get_tenant_scoped_db
from app.core.rbac import require
from app.core.responses import ApiResponse, Meta
from app.services import case_service, client_service
from app.schemas.case import CaseOut
from app.schemas.client import ClientCreateIn, ClientOut, ClientUpdateIn

router = APIRouter(prefix="/clients", tags=["Clients"])


@router.get("", response_model=ApiResponse[list[ClientOut]])
async def list_clients(
    q: str | None = None,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    auth: AuthContext = Depends(require("clients.read")),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[list[ClientOut]]:
    tenant = auth.as_tenant_context()
    clients, total = await client_service.list_clients(
        session, tenant, q=q, limit=limit, offset=(page - 1) * limit
    )
    return ApiResponse(
        success=True,
        data=[ClientOut.model_validate(c) for c in clients],
        meta=Meta(page=page, limit=limit, total=total),
    )


@router.post("", response_model=ApiResponse[ClientOut])
async def create_client(
    payload: ClientCreateIn,
    auth: AuthContext = Depends(require("clients.write")),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[ClientOut]:
    tenant = auth.as_tenant_context()
    client = await client_service.create_client(
        session,
        tenant,
        name=payload.name,
        phone=payload.phone,
        email=payload.email,
        address=payload.address,
        tags=payload.tags,
    )
    return ApiResponse(success=True, data=ClientOut.model_validate(client))


@router.get("/{client_id}", response_model=ApiResponse[ClientOut])
async def get_client(
    client_id: UUID,
    auth: AuthContext = Depends(require("clients.read")),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[ClientOut]:
    tenant = auth.as_tenant_context()
    client = await client_service.get_client_or_404(session, tenant, client_id)
    return ApiResponse(success=True, data=ClientOut.model_validate(client))


@router.patch("/{client_id}", response_model=ApiResponse[ClientOut])
async def update_client(
    client_id: UUID,
    payload: ClientUpdateIn,
    auth: AuthContext = Depends(require("clients.write")),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[ClientOut]:
    tenant = auth.as_tenant_context()
    client = await client_service.get_client_or_404(session, tenant, client_id)
    client = await client_service.update_client(session, client, **payload.model_dump())
    return ApiResponse(success=True, data=ClientOut.model_validate(client))


@router.delete("/{client_id}", response_model=ApiResponse[dict])
async def delete_client(
    client_id: UUID,
    auth: AuthContext = Depends(require("clients.write")),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[dict]:
    tenant = auth.as_tenant_context()
    client = await client_service.get_client_or_404(session, tenant, client_id)
    await client_service.delete_client(session, client)
    return ApiResponse(success=True, data={"deleted": True})


@router.post("/{client_id}/invite", response_model=ApiResponse[ClientOut])
async def invite_client(
    client_id: UUID,
    auth: AuthContext = Depends(require("clients.write")),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[ClientOut]:
    tenant = auth.as_tenant_context()
    client = await client_service.get_client_or_404(session, tenant, client_id)
    client = await client_service.invite_client(session, tenant, client)
    return ApiResponse(success=True, data=ClientOut.model_validate(client))


@router.get("/{client_id}/cases", response_model=ApiResponse[list[CaseOut]])
async def get_client_cases(
    client_id: UUID,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    auth: AuthContext = Depends(require("cases.read.assigned")),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[list[CaseOut]]:
    tenant = auth.as_tenant_context()
    # Confirms the client exists (and belongs to this tenant) before listing.
    await client_service.get_client_or_404(session, tenant, client_id)

    cases, total = await case_service.list_cases(
        session, tenant, client_id=client_id, limit=limit, offset=(page - 1) * limit
    )
    return ApiResponse(
        success=True,
        data=[CaseOut.model_validate(c) for c in cases],
        meta=Meta(page=page, limit=limit, total=total),
    )
