from datetime import timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import QuotaExceededException, ValidationException
from app.core.security import utcnow
from app.db.enums import AIJobStatus, NotificationType
from app.db.tenant import TenantContext
from app.models.ai_job import AIJob
from app.services import notification_service

settings = get_settings()

# Contract B.7: job states are "queued|running|done|failed" over the
# wire, but the DB enum (from module M2) uses pending/running/
# completed/failed internally. Map at the API boundary rather than
# rename the enum (same policy as CaseStatus's known deviation).
STATUS_WIRE_MAP: dict[AIJobStatus, str] = {
    AIJobStatus.PENDING: "queued",
    AIJobStatus.RUNNING: "running",
    AIJobStatus.COMPLETED: "done",
    AIJobStatus.FAILED: "failed",
}

TIMEOUT_SECONDS_BY_TYPE: dict[str, int] = {
    "summarize": settings.ai_summarize_timeout_seconds,
    "research": settings.ai_research_timeout_seconds,
    "draft": settings.ai_draft_timeout_seconds,
    "risk_review": settings.ai_risk_review_timeout_seconds,
}

ESTIMATED_SECONDS_BY_TYPE: dict[str, int] = {
    "summarize": 60,
    "research": 45,
    "draft": 60,
    "risk_review": 60,
}


def wire_status(status: AIJobStatus) -> str:
    return STATUS_WIRE_MAP[status]


async def _enforce_quotas(session: AsyncSession, tenant: TenantContext) -> None:
    in_flight_stmt = (
        select(func.count())
        .select_from(AIJob)
        .where(AIJob.tenant_id == tenant.tenant_id)
        .where(AIJob.status.in_([AIJobStatus.PENDING, AIJobStatus.RUNNING]))
    )
    in_flight = (await session.execute(in_flight_stmt)).scalar_one()

    if in_flight >= settings.ai_max_concurrent_jobs_per_tenant:
        raise QuotaExceededException(
            message="Too many AI jobs are already running for this firm.",
            details={
                "limit": settings.ai_max_concurrent_jobs_per_tenant,
                "plan": "default",
                "upgrade_to": None,
            },
        )

    since = utcnow() - timedelta(days=1)
    today_stmt = (
        select(func.count())
        .select_from(AIJob)
        .where(AIJob.tenant_id == tenant.tenant_id)
        .where(AIJob.created_at >= since)
    )
    today_count = (await session.execute(today_stmt)).scalar_one()

    if today_count >= settings.ai_daily_job_quota_per_tenant:
        raise QuotaExceededException(
            message="Daily AI job quota reached for this firm.",
            details={
                "limit": settings.ai_daily_job_quota_per_tenant,
                "plan": "default",
                "upgrade_to": None,
            },
        )


async def create_job(
    session: AsyncSession,
    tenant: TenantContext,
    *,
    user_id: UUID,
    type: str,
    input: dict,
) -> AIJob:
    """
    Creates an AIJob row (status=queued) and enqueues the Celery task
    that will run it. Callers get back immediately (202 Accepted
    pattern, contract B.7); the route layer is responsible for not
    awaiting job completion.
    """
    await _enforce_quotas(session, tenant)

    job = AIJob(
        tenant_id=tenant.tenant_id,
        user_id=user_id,
        type=type,
        status=AIJobStatus.PENDING,
        input=input,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)

    from app.workers.ai_worker import run_ai_job

    run_ai_job.delay(str(job.id), str(tenant.tenant_id), type)

    return job


async def get_job_or_404(session: AsyncSession, tenant: TenantContext, job_id: UUID) -> AIJob:
    result = await session.execute(
        select(AIJob).where(AIJob.id == job_id).where(AIJob.tenant_id == tenant.tenant_id)
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise ValidationException("AI job not found.")
    return job


async def mark_running(session: AsyncSession, job: AIJob) -> None:
    job.status = AIJobStatus.RUNNING
    await session.commit()


async def mark_completed(session: AsyncSession, job: AIJob, *, result: dict) -> None:
    job.status = AIJobStatus.COMPLETED
    job.result = result
    job.error = None
    await session.commit()

    await notification_service.notify_user(
        session,
        tenant_id=job.tenant_id,
        user_id=job.user_id,
        type=NotificationType.AI_JOB_COMPLETE,
        payload={"job_id": str(job.id), "job_type": job.type},
    )
    await session.commit()


async def mark_failed(session: AsyncSession, job: AIJob, *, error: str) -> None:
    job.status = AIJobStatus.FAILED
    job.error = error[:2000]
    await session.commit()
