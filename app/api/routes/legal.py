from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AuthContext, get_current_auth, get_tenant_scoped_db
from app.core.responses import ApiResponse
from app.schemas.legal import ConsentIn, ConsentStatusOut, ConsentTextOut, DataRequestOut
from app.services import consent_service, dpdp_service

router = APIRouter(prefix="/legal", tags=["Legal / DPDP"])


def _out(request, *, with_link: bool = False) -> DataRequestOut:
    out = DataRequestOut.model_validate(request)
    if with_link:
        out.download_url = dpdp_service.export_download_url(request)
    return out


@router.get("/consent-text", response_model=ApiResponse[ConsentTextOut])
async def get_consent_text(lang: str = Query(default="en")) -> ApiResponse[ConsentTextOut]:
    """Unauthenticated: the onboarding screen needs it before login completes (contract B.11)."""
    return ApiResponse(success=True, data=ConsentTextOut(**consent_service.get_consent_text(lang)))


@router.get("/consent", response_model=ApiResponse[ConsentStatusOut])
async def get_consent_status(
    auth: AuthContext = Depends(get_current_auth),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[ConsentStatusOut]:
    accepted = await consent_service.has_current_consent(session, auth.user_id)
    return ApiResponse(
        success=True,
        data=ConsentStatusOut(accepted=accepted, current_version=consent_service.CURRENT_VERSION),
    )


@router.post("/consent", response_model=ApiResponse[ConsentStatusOut])
async def accept_consent(
    payload: ConsentIn,
    auth: AuthContext = Depends(get_current_auth),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[ConsentStatusOut]:
    await consent_service.record_consent(
        session, auth.user_id, version=payload.version, language=payload.language
    )
    return ApiResponse(
        success=True,
        data=ConsentStatusOut(accepted=True, current_version=consent_service.CURRENT_VERSION),
    )


@router.post("/export", response_model=ApiResponse[DataRequestOut], status_code=202)
async def request_export(
    auth: AuthContext = Depends(get_current_auth),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[DataRequestOut]:
    from app.workers.dpdp_worker import dispatch_export

    request = await dpdp_service.create_export_request(session, auth.as_tenant_context())
    dispatch_export(request.id, request.tenant_id)
    return ApiResponse(success=True, data=_out(request))


@router.post("/delete-request", response_model=ApiResponse[DataRequestOut], status_code=202)
async def request_deletion(
    auth: AuthContext = Depends(get_current_auth),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[DataRequestOut]:
    request = await dpdp_service.create_delete_request(session, auth.as_tenant_context())
    return ApiResponse(success=True, data=_out(request))


@router.delete("/delete-request", response_model=ApiResponse[DataRequestOut])
async def cancel_deletion(
    auth: AuthContext = Depends(get_current_auth),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[DataRequestOut]:
    request = await dpdp_service.cancel_delete_request(session, auth.as_tenant_context())
    return ApiResponse(success=True, data=_out(request))


@router.get("/requests", response_model=ApiResponse[list[DataRequestOut]])
async def list_requests(
    auth: AuthContext = Depends(get_current_auth),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[list[DataRequestOut]]:
    requests = await dpdp_service.list_requests(session, auth.as_tenant_context())
    return ApiResponse(success=True, data=[_out(r) for r in requests])


@router.get("/requests/{request_id}", response_model=ApiResponse[DataRequestOut])
async def get_request(
    request_id: UUID,
    auth: AuthContext = Depends(get_current_auth),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[DataRequestOut]:
    request = await dpdp_service.get_request_or_404(session, auth.as_tenant_context(), request_id)
    return ApiResponse(success=True, data=_out(request, with_link=True))
