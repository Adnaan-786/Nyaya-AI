"""B.7 async AI job pattern, plus the summarizer and researcher.

Every AI endpoint returns **202 immediately** with a job id and an estimate; the work
runs in the background and the app either polls `GET /ai/jobs/{id}` or waits for the
`ai_job_complete` push. That shape is the contract, and it exists because a
40-page OCR summary takes far longer than any request should be held open for.

`GET /ai/jobs` (list) was one of the three endpoints I filed as missing from B.6 —
D.8 requires a "Recent AI results" list in the AI hub. Now that both halves are ours,
it is simply added here.
"""

import datetime as dt
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Page, get_scoped_or_404, paginate
from app.core import envelope, security
from app.core.db import SessionFactory, get_session, scoped
from app.integrations import fcm, llm
from app.models import AiJob, Document
from app.schemas.ai import AiJobOut, JobAcceptedOut, ResearchRequest, SummarizeRequest

router = APIRouter(tags=["ai"])

# B.14 plan limits. Hard-coded per plan until the billing module owns them.
DAILY_JOB_LIMITS = {"solo": 20, "firm": 200, "enterprise": 2000}

ESTIMATE_SECONDS = {"summarize": 45, "research": 30}


async def _enforce_quota(
    session: AsyncSession, principal: security.Principal, plan: str
) -> None:
    """B.14: a 402 must carry limit, plan and upgrade_to so the app can open the
    paywall with the right plan preselected."""
    limit = DAILY_JOB_LIMITS.get(plan, DAILY_JOB_LIMITS["solo"])
    since = dt.datetime.now(dt.UTC) - dt.timedelta(days=1)

    used = (
        await session.scalars(
            scoped(AiJob, principal.tenant_id).where(AiJob.created_at >= since)
        )
    ).all()

    if len(used) >= limit:
        upgrade_to = "firm" if plan == "solo" else "enterprise"
        raise envelope.quota_exceeded(
            f"You have used all {limit} AI requests for today.",
            limit=limit,
            plan=plan,
            upgrade_to=upgrade_to,
        )


async def _create_job(
    session: AsyncSession,
    principal: security.Principal,
    job_type: str,
    payload: dict,
) -> AiJob:
    from app.models import Tenant

    tenant = await session.get(Tenant, principal.tenant_id)
    await _enforce_quota(session, principal, tenant.plan if tenant else "solo")

    job = AiJob(
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        type=job_type,
        status="queued",
        input=payload,
        estimated_seconds=ESTIMATE_SECONDS.get(job_type, 60),
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


def _accepted(job: AiJob) -> dict:
    return JobAcceptedOut(
        job_id=job.id, status=job.status, estimated_seconds=job.estimated_seconds
    ).model_dump(mode="json")


@router.post("/ai/summarize", status_code=202)
async def summarize(
    body: SummarizeRequest,
    background: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.require_staff),
):
    document = await get_scoped_or_404(
        session, Document, body.document_id, principal.tenant_id, "document"
    )

    # Fail fast rather than queueing a job that is certain to fail: the app can show
    # "this document has no readable text yet" instead of a 45-second spinner.
    if document.ocr_status != "done" or not document.ocr_text:
        raise envelope.validation(
            "This document has no extracted text yet. Try again once processing finishes."
        )

    job = await _create_job(
        session,
        principal,
        "summarize",
        {"document_id": str(body.document_id), "doc_type_hint": body.doc_type_hint},
    )
    background.add_task(run_job, job.id)
    return envelope.ok(_accepted(job))


@router.post("/ai/research", status_code=202)
async def research(
    body: ResearchRequest,
    background: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.require_staff),
):
    job = await _create_job(
        session,
        principal,
        "research",
        {"query": body.query, "language": body.language},
    )
    background.add_task(run_job, job.id)
    return envelope.ok(_accepted(job))


@router.get("/ai/jobs")
async def list_jobs(
    type: str | None = Query(None, pattern="^(summarize|research|draft|risk_review)$"),
    page: Page = Depends(),
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.require_staff),
):
    """D.8's "Recent AI results" list. Scoped to the requesting user, not the firm —
    another lawyer's research history is not this lawyer's business."""
    statement = scoped(AiJob, principal.tenant_id).where(AiJob.user_id == principal.user_id)
    if type:
        statement = statement.where(AiJob.type == type)
    statement = statement.order_by(AiJob.created_at.desc())

    rows, meta = await paginate(session, statement, page)
    return envelope.ok(
        [AiJobOut.model_validate(r).model_dump(mode="json") for r in rows], meta
    )


@router.get("/ai/jobs/{job_id}")
async def get_job(
    job_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.require_staff),
):
    job = await get_scoped_or_404(session, AiJob, job_id, principal.tenant_id, "job")
    return envelope.ok(AiJobOut.model_validate(job).model_dump(mode="json"))


async def run_job(job_id: uuid.UUID) -> None:
    """The background worker. Opens its own session — the request's is closed."""
    async with SessionFactory() as session:
        job = await session.get(AiJob, job_id)
        if job is None:
            return

        job.status = "running"
        await session.commit()

        try:
            result = await _dispatch(session, job)
            job.result = result
            job.status = "done"
            job.error = None
        except llm.LlmRefusal as exc:
            job.status = "failed"
            job.error = str(exc)
        except Exception as exc:  # noqa: BLE001
            # A provider outage must fail this job, not take the worker down with it.
            job.status = "failed"
            job.error = "The AI service is temporarily unavailable. Please try again."
            _log_failure(job_id, exc)

        job.completed_at = dt.datetime.now(dt.UTC)
        await session.commit()

        # B.8: the push is what lets a lawyer background the app during a 45-second
        # job and still be brought back to the result. Polling is only the fallback.
        await fcm.send_to_user(
            session,
            user_id=job.user_id,
            tenant_id=job.tenant_id,
            push_type=fcm.AI_JOB_COMPLETE,
            title=(
                "Your summary is ready" if job.type == "summarize" else "Your research is ready"
            ),
            body=_push_preview(job),
            deep_link=f"nyayaai://job/{job.id}",
        )
        await session.commit()


def _push_preview(job) -> str:
    """One line of the actual result, so the notification says something."""
    if job.status == "failed":
        return job.error or "The job could not be completed."
    result = job.result or {}
    text = result.get("summary_markdown") or result.get("answer_markdown") or ""
    return (text[:120] + "...") if len(text) > 120 else (text or "Tap to open.")


def _log_failure(job_id: uuid.UUID, exc: Exception) -> None:
    import logging

    logging.getLogger(__name__).exception("ai job %s failed: %s", job_id, exc)


async def _dispatch(session: AsyncSession, job: AiJob) -> dict:
    if job.type == "summarize":
        document = await session.get(Document, uuid.UUID(job.input["document_id"]))
        if document is None or not document.ocr_text:
            raise llm.LlmRefusal("That document is no longer available.")
        summary = await llm.summarize_document(
            document.ocr_text, job.input.get("doc_type_hint")
        )
        return summary.model_dump(mode="json")

    if job.type == "research":
        answer = await llm.research_case_law(job.input["query"], job.input["language"])
        return answer.model_dump(mode="json")

    raise llm.LlmRefusal(f"Unsupported job type: {job.type}")
