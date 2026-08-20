"""
AI job execution (plan C.9): one Celery task drives every AI job type
through the same queued -> running -> done|failed lifecycle (contract
B.7), dispatching to a per-type handler via `_HANDLERS`. All four job
types (summarize, risk_review, draft, research) are implemented.

Same asyncio-inside-sync-Celery-task + per-tenant RLS pattern as
app/workers/ecourts_worker.py and app/workers/document_worker.py.
"""

import asyncio
from uuid import UUID

import sentry_sdk
from sqlalchemy import select

from app.ai import researcher, risk_review, summarizer
from app.core.logging import get_logger
from app.db.rls import set_tenant
from app.db.session import AsyncSessionLocal
from app.db.tenant import TenantContext
from app.models.ai_job import AIJob
from app.models.case import Case
from app.models.doc_chunk import DocChunk
from app.models.document import Document
from app.models.user import User
from app.services import ai_job_service, conversation_service, draft_service
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


async def _handle_summarize(session, tenant: TenantContext, job: AIJob, language: str) -> dict:
    document_id = job.input.get("document_id")
    if not document_id:
        raise ValueError("summarize job is missing input.document_id")

    result = await session.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    if document is None:
        raise ValueError(f"document {document_id} not found")

    chunks_result = await session.execute(
        select(DocChunk)
        .where(DocChunk.document_id == document.id)
        .order_by(DocChunk.chunk_index.asc())
    )
    chunk_texts = [c.text for c in chunks_result.scalars().all()]

    return await summarizer.summarize_document(
        text=document.extracted_text or "",
        chunks=chunk_texts or None,
        language=language,
    )


async def _handle_risk_review(session, tenant: TenantContext, job: AIJob, language: str) -> dict:
    document_id = job.input.get("document_id")
    if not document_id:
        raise ValueError("risk_review job is missing input.document_id")

    result = await session.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    if document is None:
        raise ValueError(f"document {document_id} not found")

    return await risk_review.review_document(document.extracted_text or "")


async def _handle_draft(session, tenant: TenantContext, job: AIJob, language: str) -> dict:
    template_id = job.input.get("template_id")
    if not template_id:
        raise ValueError("draft job is missing input.template_id")

    fields = job.input.get("fields") or {}
    case_id = job.input.get("case_id")

    case = None
    if case_id:
        result = await session.execute(select(Case).where(Case.id == case_id))
        case = result.scalar_one_or_none()

    return await draft_service.draft_document(
        tenant=tenant,
        job_id=job.id,
        template_id=template_id,
        case=case,
        fields=fields,
        language=language,
    )


async def _handle_research(session, tenant: TenantContext, job: AIJob, language: str) -> dict:
    query = job.input.get("query")
    conversation_id = job.input.get("conversation_id")
    if not query or not conversation_id:
        raise ValueError("research job is missing input.query or input.conversation_id")

    from uuid import UUID as _UUID

    conversation = await conversation_service.get_conversation_or_404(
        session, tenant, _UUID(conversation_id)
    )
    context_query = conversation_service.build_context_query(conversation, query)

    result = await researcher.research(
        query=context_query, language=job.input.get("language") or language
    )

    await conversation_service.append_turn(session, conversation, query=query, result=result)

    return result


_HANDLERS = {
    "summarize": _handle_summarize,
    "risk_review": _handle_risk_review,
    "draft": _handle_draft,
    "research": _handle_research,
}


async def _run_job(job_id: str, tenant_id: str, job_type: str) -> str:
    async with AsyncSessionLocal() as session:
        await set_tenant(session, tenant_id)
        # user_id is unused by the handlers below (only tenant_id is
        # read); there's no "current user" in a background job.
        tenant = TenantContext(tenant_id=UUID(tenant_id), user_id=UUID(tenant_id))

        result = await session.execute(select(AIJob).where(AIJob.id == job_id))
        job = result.scalar_one_or_none()
        if job is None:
            logger.warning("ai_worker_missing_job", job_id=job_id)
            return "missing"

        handler = _HANDLERS.get(job_type)
        if handler is None:
            await ai_job_service.mark_failed(
                session, job, error=f"Job type {job_type!r} is not yet implemented."
            )
            return "unsupported_type"

        user_result = await session.execute(select(User).where(User.id == job.user_id))
        user = user_result.scalar_one_or_none()
        language = user.language if user else "en"

        await ai_job_service.mark_running(session, job)

        timeout = ai_job_service.TIMEOUT_SECONDS_BY_TYPE.get(job_type, 300)

        try:
            result_data = await asyncio.wait_for(
                handler(session, tenant, job, language), timeout=timeout
            )
            await ai_job_service.mark_completed(session, job, result=result_data)
            return "done"

        except TimeoutError:
            await session.rollback()
            reloaded = await session.execute(select(AIJob).where(AIJob.id == job_id))
            job = reloaded.scalar_one_or_none()
            if job is not None:
                await ai_job_service.mark_failed(
                    session, job, error=f"Job timed out after {timeout}s."
                )
            return "timeout"

        except Exception as exc:  # noqa: BLE001
            await session.rollback()
            reloaded = await session.execute(select(AIJob).where(AIJob.id == job_id))
            job = reloaded.scalar_one_or_none()
            if job is not None:
                await ai_job_service.mark_failed(session, job, error=str(exc))
            sentry_sdk.capture_exception(exc)
            logger.exception("ai_job_failed", job_id=job_id, job_type=job_type, error=str(exc))
            return "failed"


@celery_app.task(name="app.workers.ai_worker.run_ai_job")
def run_ai_job(job_id: str, tenant_id: str, job_type: str):
    return asyncio.run(_run_job(job_id, tenant_id, job_type))
