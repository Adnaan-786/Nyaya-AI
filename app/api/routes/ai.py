from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AuthContext, get_tenant_scoped_db
from app.core.rbac import require
from app.core.responses import ApiResponse
from app.schemas.ai import AIJobAcceptedOut, AIJobOut, SummarizeIn
from app.services import ai_job_service, document_service

router = APIRouter(prefix="/ai", tags=["AI"])


@router.post("/summarize", response_model=ApiResponse[AIJobAcceptedOut], status_code=202)
async def summarize(
    payload: SummarizeIn,
    auth: AuthContext = Depends(require("ai.summarize")),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[AIJobAcceptedOut]:
    tenant = auth.as_tenant_context()

    # Confirms the document exists (and belongs to this tenant) before
    # queuing work for it.
    await document_service.get_document_or_404(session, tenant, payload.document_id)

    job = await ai_job_service.create_job(
        session,
        tenant,
        user_id=auth.user_id,
        type="summarize",
        input={
            "document_id": str(payload.document_id),
            "doc_type_hint": payload.doc_type_hint,
        },
    )

    return ApiResponse(
        success=True,
        data=AIJobAcceptedOut(
            job_id=job.id,
            estimated_seconds=ai_job_service.ESTIMATED_SECONDS_BY_TYPE.get("summarize", 60),
        ),
    )


@router.get("/jobs/{job_id}", response_model=ApiResponse[AIJobOut])
async def get_job(
    job_id: UUID,
    auth: AuthContext = Depends(require("ai.jobs.read")),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[AIJobOut]:
    tenant = auth.as_tenant_context()
    job = await ai_job_service.get_job_or_404(session, tenant, job_id)
    return ApiResponse(success=True, data=AIJobOut.from_model(job))
