from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import AuthenticationException
from app.core.responses import ApiResponse
from app.db.session import get_db
from app.schemas.app_config import AppConfigOut, AppConfigUpdateIn
from app.services import app_config_service

router = APIRouter(prefix="/app", tags=["App Config"])


@router.get("/config", response_model=ApiResponse[AppConfigOut])
async def get_app_config(session: AsyncSession = Depends(get_db)) -> ApiResponse[AppConfigOut]:
    """Unauthenticated -- contract B.14: called on every cold start, cached 6h client-side."""
    row = await app_config_service.get_or_create(session)
    return ApiResponse(success=True, data=AppConfigOut.model_validate(row))


@router.patch("/config", response_model=ApiResponse[AppConfigOut])
async def update_app_config(
    payload: AppConfigUpdateIn,
    x_admin_key: str | None = Header(default=None),
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[AppConfigOut]:
    """
    Platform-wide (not per-firm), so gated by a shared-secret header
    rather than tenant RBAC. No NyayaAI-staff auth system exists yet;
    this is a documented placeholder (see ADMIN_API_KEY).
    """
    settings = get_settings()
    if not settings.admin_api_key or x_admin_key != settings.admin_api_key:
        raise AuthenticationException("Invalid or missing admin key.")
    row = await app_config_service.get_or_create(session)
    row = await app_config_service.update(session, row, **payload.model_dump())
    return ApiResponse(success=True, data=AppConfigOut.model_validate(row))
