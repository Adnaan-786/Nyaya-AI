from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AuthContext, get_current_auth, get_tenant_scoped_db
from app.core.responses import ApiResponse
from app.services import search_service

router = APIRouter(tags=["Search"])


@router.get("/search", response_model=ApiResponse[dict])
async def universal_search(
    q: str = Query(..., min_length=1),
    type: Literal["all", "cases", "clients", "documents"] = "all",
    limit: int = Query(default=10, ge=1, le=50),
    auth: AuthContext = Depends(get_current_auth),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[dict]:
    tenant = auth.as_tenant_context()
    results = await search_service.universal_search(
        session, tenant, q=q, type_filter=type, limit=limit
    )
    return ApiResponse(success=True, data=results)
