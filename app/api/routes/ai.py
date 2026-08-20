from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.templates import list_templates
from app.core.dependencies import AuthContext, get_tenant_scoped_db
from app.core.rbac import require
from app.core.responses import ApiResponse
from app.schemas.ai import (
    AIJobAcceptedOut,
    AIJobOut,
    ConversationMessageOut,
    ConversationOut,
    DraftIn,
    ResearchIn,
    RiskReviewIn,
    SummarizeIn,
    TemplateFieldOut,
    TemplateOut,
)
from app.services import ai_job_service, case_service, conversation_service, document_service
from app.services.draft_service import get_template_or_404

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


@router.post("/risk-review", response_model=ApiResponse[AIJobAcceptedOut], status_code=202)
async def risk_review(
    payload: RiskReviewIn,
    auth: AuthContext = Depends(require("ai.use")),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[AIJobAcceptedOut]:
    tenant = auth.as_tenant_context()

    await document_service.get_document_or_404(session, tenant, payload.document_id)

    job = await ai_job_service.create_job(
        session,
        tenant,
        user_id=auth.user_id,
        type="risk_review",
        input={"document_id": str(payload.document_id)},
    )

    return ApiResponse(
        success=True,
        data=AIJobAcceptedOut(
            job_id=job.id,
            estimated_seconds=ai_job_service.ESTIMATED_SECONDS_BY_TYPE.get("risk_review", 60),
        ),
    )


@router.get("/templates", response_model=ApiResponse[list[TemplateOut]])
async def get_templates(
    auth: AuthContext = Depends(require("ai.use")),
) -> ApiResponse[list[TemplateOut]]:
    templates = [
        TemplateOut(
            id=t.id,
            name=t.name,
            category=t.category,
            fields=[
                TemplateFieldOut(name=f.name, label=f.label, type=f.type, required=f.required)
                for f in t.fields
            ],
        )
        for t in list_templates()
    ]
    return ApiResponse(success=True, data=templates)


@router.post("/draft", response_model=ApiResponse[AIJobAcceptedOut], status_code=202)
async def draft(
    payload: DraftIn,
    auth: AuthContext = Depends(require("ai.use")),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[AIJobAcceptedOut]:
    tenant = auth.as_tenant_context()

    # Validates the template exists before queuing work.
    get_template_or_404(payload.template_id)

    if payload.case_id is not None:
        # Confirms the case exists (and belongs to this tenant).
        await case_service.get_case_or_404(session, tenant, payload.case_id)

    job = await ai_job_service.create_job(
        session,
        tenant,
        user_id=auth.user_id,
        type="draft",
        input={
            "template_id": payload.template_id,
            "case_id": str(payload.case_id) if payload.case_id else None,
            "fields": payload.fields,
        },
    )

    return ApiResponse(
        success=True,
        data=AIJobAcceptedOut(
            job_id=job.id,
            estimated_seconds=ai_job_service.ESTIMATED_SECONDS_BY_TYPE.get("draft", 60),
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


@router.post("/research", response_model=ApiResponse[AIJobAcceptedOut], status_code=202)
async def research(
    payload: ResearchIn,
    auth: AuthContext = Depends(require("ai.use")),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[AIJobAcceptedOut]:
    tenant = auth.as_tenant_context()

    # Conversation is created/validated synchronously so the caller
    # gets its id back immediately, even for a brand-new conversation
    # (contract B.6: POST /ai/research accepts an optional
    # conversation_id; follow-ups reuse it).
    conversation = await conversation_service.get_or_create_conversation(
        session, tenant, user_id=auth.user_id, conversation_id=payload.conversation_id
    )

    job = await ai_job_service.create_job(
        session,
        tenant,
        user_id=auth.user_id,
        type="research",
        input={
            "query": payload.query,
            "language": payload.language,
            "conversation_id": str(conversation.id),
        },
    )

    return ApiResponse(
        success=True,
        data=AIJobAcceptedOut(
            job_id=job.id,
            estimated_seconds=ai_job_service.ESTIMATED_SECONDS_BY_TYPE.get("research", 60),
            conversation_id=conversation.id,
        ),
    )


@router.get("/conversations/{conversation_id}", response_model=ApiResponse[ConversationOut])
async def get_conversation(
    conversation_id: UUID,
    auth: AuthContext = Depends(require("ai.use")),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[ConversationOut]:
    tenant = auth.as_tenant_context()
    conversation = await conversation_service.get_conversation_or_404(
        session, tenant, conversation_id
    )
    return ApiResponse(
        success=True,
        data=ConversationOut(
            id=conversation.id,
            created_at=conversation.created_at,
            messages=[ConversationMessageOut(**m) for m in conversation.messages],
        ),
    )
