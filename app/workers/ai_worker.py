"""
AI job execution (plan C.9): one Celery task drives every AI job type
through the same queued -> running -> done|failed lifecycle (contract
B.7), dispatching to a per-type handler. Only "summarize" is
implemented so far -- research/draft/risk_review are future additions
to `_HANDLERS` below; nothing else about the framework needs to change
when they land.

Same asyncio-inside-sync-Celery-task + per-tenant RLS pattern as
app/workers/ecourts_worker.py and app/workers/document_worker.py.
"""

import asyncio
from uuid import UUID

import sentry_sdk
from sqlalchemy import select

from app.ai import summarizer
from app.core.logging import get_logger
from app.db.rls import set_tenant
from app.db.session import AsyncSessionLocal
from app.db.tenant import TenantContext
from app.models.ai_job import AIJob
from app.models.doc_chunk import DocChunk
from app.models.document import Document
from app.models.user import User
from app.services import ai_job_service
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


_HANDLERS = {
    "summarize": _handle_summarize,
    # "research": _handle_research,      # future addition
    # "draft": _handle_draft,            # future addition
    # "risk_review": _handle_risk_review,  # future addition
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
