from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AuthContext, get_tenant_scoped_db
from app.core.rbac import require
from app.core.responses import ApiResponse, Meta
from app.schemas.case import (
    CaseCreateIn,
    CaseNoteCreateIn,
    CaseNoteOut,
    CaseOut,
    CaseUpdateIn,
    CaseFromCNRIn,
    CNRHearingHistoryOut,
    CNRLookupIn,
    CNRLookupPreviewOut,
    HearingCreateIn,
    HearingOut,
    HearingUpdateIn,
    TimelineEventOut,
)
from app.services import case_service, ecourts_service, hearing_service

router = APIRouter(tags=["Cases"])


@router.get("/cases", response_model=ApiResponse[list[CaseOut]])
async def list_cases(
    status: str | None = None,
    court: str | None = None,
    assigned_to: UUID | None = None,
    q: str | None = None,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    auth: AuthContext = Depends(require("cases.read.assigned")),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[list[CaseOut]]:
    tenant = auth.as_tenant_context()
    cases, total = await case_service.list_cases(
        session,
        tenant,
        status=status,
        court=court,
        assigned_to=assigned_to,
        q=q,
        limit=limit,
        offset=(page - 1) * limit,
    )
    return ApiResponse(
        success=True,
        data=[CaseOut.model_validate(c) for c in cases],
        meta=Meta(page=page, limit=limit, total=total),
    )


@router.post("/cases", response_model=ApiResponse[CaseOut])
async def create_case(
    payload: CaseCreateIn,
    auth: AuthContext = Depends(require("cases.write")),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[CaseOut]:
    tenant = auth.as_tenant_context()
    case = await case_service.create_case(
        session,
        tenant,
        title=payload.title,
        client_id=payload.client_id,
        case_number=payload.case_number,
        court_name=payload.court_name,
        court_type=payload.court_type,
        judge_name=payload.judge_name,
        case_type=payload.case_type,
        stage=payload.stage,
        next_hearing_date=payload.next_hearing_date,
        assigned_user_ids=payload.assigned_user_ids,
    )
    return ApiResponse(success=True, data=CaseOut.model_validate(case))


@router.post("/cases/lookup-cnr", response_model=ApiResponse[CNRLookupPreviewOut])
async def lookup_cnr(
    payload: CNRLookupIn,
    auth: AuthContext = Depends(require("cases.write")),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[CNRLookupPreviewOut]:
    normalized = await ecourts_service.lookup_cnr(session, payload.cnr)
    return ApiResponse(
        success=True,
        data=CNRLookupPreviewOut(
            cnr=normalized.cnr,
            title=normalized.title,
            court_name=normalized.court_name,
            court_type=normalized.court_type,
            judge_name=normalized.judge_name,
            case_type=normalized.case_type,
            stage=normalized.stage,
            parties=normalized.parties,
            next_hearing_date=normalized.next_hearing_date,
            history=[
                CNRHearingHistoryOut(
                    date=h.date, purpose=h.purpose, outcome_notes=h.outcome_notes
                )
                for h in normalized.history
            ],
        ),
    )


@router.post("/cases/from-cnr", response_model=ApiResponse[CaseOut])
async def create_case_from_cnr(
    payload: CaseFromCNRIn,
    auth: AuthContext = Depends(require("cases.write")),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[CaseOut]:
    tenant = auth.as_tenant_context()
    case = await ecourts_service.create_case_from_cnr(
        session, tenant, cnr=payload.cnr, client_id=payload.client_id
    )
    return ApiResponse(success=True, data=CaseOut.model_validate(case))


@router.get("/cases/{case_id}", response_model=ApiResponse[CaseOut])
async def get_case(
    case_id: UUID,
    auth: AuthContext = Depends(require("cases.read.assigned")),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[CaseOut]:
    tenant = auth.as_tenant_context()
    case = await case_service.get_case_or_404(session, tenant, case_id)
    return ApiResponse(success=True, data=CaseOut.model_validate(case))


@router.patch("/cases/{case_id}", response_model=ApiResponse[CaseOut])
async def update_case(
    case_id: UUID,
    payload: CaseUpdateIn,
    auth: AuthContext = Depends(require("cases.write")),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[CaseOut]:
    tenant = auth.as_tenant_context()
    case = await case_service.get_case_or_404(session, tenant, case_id)
    case = await case_service.update_case(session, case, **payload.model_dump())
    return ApiResponse(success=True, data=CaseOut.model_validate(case))


@router.delete("/cases/{case_id}", response_model=ApiResponse[dict])
async def delete_case(
    case_id: UUID,
    auth: AuthContext = Depends(require("cases.write")),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[dict]:
    tenant = auth.as_tenant_context()
    case = await case_service.get_case_or_404(session, tenant, case_id)
    await case_service.delete_case(session, case)
    return ApiResponse(success=True, data={"archived": True})


@router.post("/cases/{case_id}/sync", response_model=ApiResponse[CaseOut])
async def force_sync_case(
    case_id: UUID,
    auth: AuthContext = Depends(require("cases.write")),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[CaseOut]:
    tenant = auth.as_tenant_context()
    case = await case_service.get_case_or_404(session, tenant, case_id)
    case = await ecourts_service.sync_case(session, tenant, case)
    return ApiResponse(success=True, data=CaseOut.model_validate(case))


@router.get("/cases/{case_id}/hearings", response_model=ApiResponse[list[HearingOut]])
async def list_hearings(
    case_id: UUID,
    auth: AuthContext = Depends(require("cases.read.assigned")),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[list[HearingOut]]:
    tenant = auth.as_tenant_context()
    await case_service.get_case_or_404(session, tenant, case_id)
    hearings = await hearing_service.list_hearings(session, tenant, case_id)
    return ApiResponse(success=True, data=[HearingOut.model_validate(h) for h in hearings])


@router.post("/cases/{case_id}/hearings", response_model=ApiResponse[HearingOut])
async def create_hearing(
    case_id: UUID,
    payload: HearingCreateIn,
    auth: AuthContext = Depends(require("cases.write")),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[HearingOut]:
    tenant = auth.as_tenant_context()
    await case_service.get_case_or_404(session, tenant, case_id)
    hearing = await hearing_service.create_hearing(
        session,
        tenant,
        case_id,
        date=payload.date,
        time=payload.time,
        purpose=payload.purpose,
        courtroom=payload.courtroom,
    )
    return ApiResponse(success=True, data=HearingOut.model_validate(hearing))


@router.patch("/hearings/{hearing_id}", response_model=ApiResponse[HearingOut])
async def update_hearing(
    hearing_id: UUID,
    payload: HearingUpdateIn,
    auth: AuthContext = Depends(require("cases.write")),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[HearingOut]:
    tenant = auth.as_tenant_context()
    hearing = await hearing_service.get_hearing_or_404(session, tenant, hearing_id)
    hearing = await hearing_service.update_hearing(session, hearing, **payload.model_dump())
    return ApiResponse(success=True, data=HearingOut.model_validate(hearing))


@router.get("/cases/{case_id}/timeline", response_model=ApiResponse[list[TimelineEventOut]])
async def get_case_timeline(
    case_id: UUID,
    auth: AuthContext = Depends(require("cases.read.assigned")),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[list[TimelineEventOut]]:
    tenant = auth.as_tenant_context()
    await case_service.get_case_or_404(session, tenant, case_id)
    events = await hearing_service.get_case_timeline(session, tenant, case_id)
    return ApiResponse(success=True, data=[TimelineEventOut(**e) for e in events])


@router.post("/cases/{case_id}/notes", response_model=ApiResponse[CaseNoteOut])
async def add_case_note(
    case_id: UUID,
    payload: CaseNoteCreateIn,
    auth: AuthContext = Depends(require("cases.notes.write")),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[CaseNoteOut]:
    tenant = auth.as_tenant_context()
    await case_service.get_case_or_404(session, tenant, case_id)
    note = await hearing_service.add_case_note(
        session, tenant, case_id, author_id=auth.user_id, text=payload.text
    )
    return ApiResponse(success=True, data=CaseNoteOut.model_validate(note))
