"""B.7 async AI job pattern: summarize, research, draft and risk review.

Every AI endpoint returns **202 immediately** with a job id and an estimate; the work
runs in the background and the app either polls `GET /ai/jobs/{id}` or waits for the
`ai_job_complete` push. That shape is the contract, and it exists because a
40-page OCR summary takes far longer than any request should be held open for.

`GET /ai/jobs` (list) was one of the three endpoints I filed as missing from B.6 —
D.8 requires a "Recent AI results" list in the AI hub. Now that both halves are ours,
it is simply added here.

The four job types differ in where their answer comes from, which is the only thing
worth keeping straight while reading `_dispatch`:

* **summarize** and **research** go to the model and are validated against their
  contract schema in `app/integrations/llm.py`. Research in particular drops any
  citation it cannot verify and forces `insufficient` confidence when none survive —
  that guarantee lives there, not here, and nothing on this path may route around it.
* **draft** fills a template's prose from fields the caller supplied, and reports what
  it was not given rather than inventing it.
* **risk_review** assesses one clause at a time, because the app renders a list.
"""

import asyncio
import datetime as dt
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import risk_review as risk_review_ai
from app.ai.templates import list_templates
from app.api.deps import Page, get_scoped_or_404, paginate
from app.core import envelope, security
from app.core.db import SessionFactory, get_session, scoped
from app.integrations import fcm, llm
from app.models import AiConversation, AiJob, Case, Document
from app.schemas.ai import (
    AiJobOut,
    ConversationCreateRequest,
    ConversationOut,
    ConversationSummaryOut,
    DraftRequest,
    JobAcceptedOut,
    ResearchRequest,
    RiskReviewRequest,
    SummarizeRequest,
    TemplateFieldOut,
    TemplateOut,
)
from app.services import ai_job_service, conversation_service, draft_service

# The plan table lives in the service now, but stays reachable under its original name
# here: this is the same dict object, so anything that reaches for `ai.DAILY_JOB_LIMITS`
# still reads and writes the limits actually being enforced.
from app.services.ai_job_service import DAILY_JOB_LIMITS

router = APIRouter(tags=["ai"])

__all__ = ["DAILY_JOB_LIMITS", "router", "run_job"]

PUSH_TITLES = {
    "summarize": "Your summary is ready",
    "research": "Your research is ready",
    "draft": "Your draft is ready",
    "risk_review": "Your risk review is ready",
}


def _accepted(job: AiJob) -> dict:
    return JobAcceptedOut(
        job_id=job.id, status=job.status, estimated_seconds=job.estimated_seconds
    ).model_dump(mode="json")


async def _require_extracted_text(
    session: AsyncSession, document_id: uuid.UUID, tenant_id: uuid.UUID
) -> Document:
    """Fail fast rather than queueing a job that is certain to fail: the app can show
    "this document has no readable text yet" instead of a 45-second spinner."""
    document = await get_scoped_or_404(session, Document, document_id, tenant_id, "document")

    if document.ocr_status != "done" or not document.ocr_text:
        raise envelope.validation(
            "This document has no extracted text yet. Try again once processing finishes."
        )
    return document


@router.post("/ai/summarize", status_code=202)
async def summarize(
    body: SummarizeRequest,
    background: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.require_staff),
):
    await _require_extracted_text(session, body.document_id, principal.tenant_id)

    job = await ai_job_service.create_job(
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
    # A conversation is only attached when the app names one. It cannot be created
    # here, because B.7 fixes this response to exactly three fields and there would be
    # no way to tell the app the id — `POST /ai/conversations` is that door.
    conversation_id = None
    if body.conversation_id is not None:
        conversation = await conversation_service.get_for_user_or_404(
            session,
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
            conversation_id=body.conversation_id,
        )
        conversation_id = conversation.id

    job = await ai_job_service.create_job(
        session,
        principal,
        "research",
        {"query": body.query, "language": body.language},
        conversation_id=conversation_id,
    )
    background.add_task(run_job, job.id)
    return envelope.ok(_accepted(job))


@router.post("/ai/draft", status_code=202)
async def draft(
    body: DraftRequest,
    background: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.require_staff),
):
    # Both checks up front, for the same reason summarize checks its document: a bad
    # template id or another firm's case must be a 400/404 the app can act on, not a
    # job that fails a minute later.
    draft_service.get_template_or_400(body.template_id)
    if body.case_id is not None:
        await get_scoped_or_404(session, Case, body.case_id, principal.tenant_id, "case")

    job = await ai_job_service.create_job(
        session,
        principal,
        "draft",
        {
            "template_id": body.template_id,
            "case_id": str(body.case_id) if body.case_id else None,
            "fields": body.fields,
            "language": body.language,
        },
    )
    background.add_task(run_job, job.id)
    return envelope.ok(_accepted(job))


@router.post("/ai/risk-review", status_code=202)
async def risk_review(
    body: RiskReviewRequest,
    background: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.require_staff),
):
    await _require_extracted_text(session, body.document_id, principal.tenant_id)

    job = await ai_job_service.create_job(
        session, principal, "risk_review", {"document_id": str(body.document_id)}
    )
    background.add_task(run_job, job.id)
    return envelope.ok(_accepted(job))


@router.get("/ai/templates")
async def get_templates(
    _: security.Principal = Depends(security.require_staff),
):
    """The draftsman catalogue. Static, but authenticated like everything else — the
    field schemas are what the app builds its drafting forms from."""
    return envelope.ok(
        [
            TemplateOut(
                id=template.id,
                name=template.name,
                category=template.category,
                fields=[
                    TemplateFieldOut(
                        name=field.name,
                        label=field.label,
                        type=field.type,
                        required=field.required,
                    )
                    for field in template.fields
                ],
            ).model_dump(mode="json")
            for template in list_templates()
        ]
    )


@router.post("/ai/conversations", status_code=201)
async def create_conversation(
    body: ConversationCreateRequest,
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.require_staff),
):
    conversation = await conversation_service.create_conversation(
        session,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        title=body.title,
    )
    return envelope.ok(ConversationOut.model_validate(conversation).model_dump(mode="json"))


@router.get("/ai/conversations")
async def list_conversations(
    page: Page = Depends(),
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.require_staff),
):
    statement = (
        scoped(AiConversation, principal.tenant_id)
        .where(AiConversation.user_id == principal.user_id)
        .order_by(AiConversation.updated_at.desc())
    )
    rows, meta = await paginate(session, statement, page)
    return envelope.ok(
        [ConversationSummaryOut.model_validate(r).model_dump(mode="json") for r in rows], meta
    )


@router.get("/ai/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.require_staff),
):
    conversation = await conversation_service.get_for_user_or_404(
        session,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        conversation_id=conversation_id,
    )
    return envelope.ok(ConversationOut.model_validate(conversation).model_dump(mode="json"))


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
            # C.9 per-type timeouts. Without one, a provider that accepts the
            # connection and then never answers leaves the job "running" forever and
            # the app spinning on it — a clean failure is far more useful than that.
            result = await asyncio.wait_for(
                _dispatch(session, job), ai_job_service.timeout_for(job.type)
            )
            job.result = result
            job.status = "done"
            job.error = None
        except llm.LlmRefusal as exc:
            await _mark_failed(session, job, str(exc))
        except TimeoutError:
            await _mark_failed(
                session, job, "This took too long and was stopped. Please try again."
            )
        except Exception as exc:  # noqa: BLE001
            # A provider outage must fail this job, not take the worker down with it.
            await _mark_failed(
                session, job, "The AI service is temporarily unavailable. Please try again."
            )
            _log_failure(job_id, exc)

        job.completed_at = dt.datetime.now(dt.UTC)
        await session.commit()

        await _record_conversation_turn(session, job)

        # B.8: the push is what lets a lawyer background the app during a 45-second
        # job and still be brought back to the result. Polling is only the fallback.
        await fcm.send_to_user(
            session,
            user_id=job.user_id,
            tenant_id=job.tenant_id,
            push_type=fcm.AI_JOB_COMPLETE,
            title=PUSH_TITLES.get(job.type, "Your AI result is ready"),
            body=_push_preview(job),
            deep_link=f"nyayaai://job/{job.id}",
        )
        await session.commit()


async def _mark_failed(session: AsyncSession, job: AiJob, message: str) -> None:
    """Roll back before recording the failure.

    A dispatch that fails part-way can leave an open transaction behind — the draft
    path writes a document row before it is done — and committing the failure on top of
    that either takes the half-written rows with it or fails outright, leaving the job
    stuck on "running" with nothing to explain why.
    """
    await session.rollback()
    await session.refresh(job)
    job.status = "failed"
    job.error = message


async def _record_conversation_turn(session: AsyncSession, job: AiJob) -> None:
    """Appends a finished research answer to its conversation, so a follow-up has the
    thread to retrieve against. Never fails the job it is recording."""
    if job.type != "research" or job.conversation_id is None or job.status != "done":
        return

    conversation = await session.get(AiConversation, job.conversation_id)
    if conversation is None:
        return

    try:
        await conversation_service.append_turn(
            session, conversation, query=job.input.get("query", ""), result=job.result or {}
        )
    except Exception as exc:  # noqa: BLE001
        _log_failure(job.id, exc)
        await session.rollback()


def _push_preview(job) -> str:
    """One line of the actual result, so the notification says something."""
    if job.status == "failed":
        return job.error or "The job could not be completed."

    result = job.result or {}
    if job.type == "risk_review":
        risks = result.get("risks") or []
        high = sum(1 for r in risks if r.get("severity") == "high")
        return f"{len(risks)} clause(s) reviewed, {high} high-risk."

    text = (
        result.get("summary_markdown")
        or result.get("answer_markdown")
        or result.get("document_markdown")
        or ""
    )
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
        query = job.input["query"]
        if job.conversation_id is not None:
            conversation = await session.get(AiConversation, job.conversation_id)
            if conversation is not None:
                query = conversation_service.build_context_query(conversation, query)
        answer = await llm.research_case_law(query, job.input["language"])
        return answer.model_dump(mode="json")

    if job.type == "risk_review":
        document = await session.get(Document, uuid.UUID(job.input["document_id"]))
        if document is None or not document.ocr_text:
            raise llm.LlmRefusal("That document is no longer available.")
        return await risk_review_ai.review_document(document.ocr_text)

    if job.type == "draft":
        case = None
        if job.input.get("case_id"):
            case = await session.get(Case, uuid.UUID(job.input["case_id"]))
            if case is None or case.tenant_id != job.tenant_id:
                raise llm.LlmRefusal("That case is no longer available.")
        return await draft_service.draft_document(
            session,
            tenant_id=job.tenant_id,
            user_id=job.user_id,
            template_id=job.input["template_id"],
            case=case,
            fields=job.input.get("fields") or {},
            language=job.input.get("language", "en"),
        )

    raise llm.LlmRefusal(f"Unsupported job type: {job.type}")
