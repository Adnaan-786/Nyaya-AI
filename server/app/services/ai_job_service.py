"""Creation and admission control for AI jobs (C.7).

Two limits, and they mean different things to the lawyer holding the phone:

* **Daily quota** is commercial. Hitting it is a 402 carrying `upgrade_to`, so the app
  opens the paywall on the right plan (B.14). The per-plan table below is what the
  deployed instance enforces; `ai_daily_job_quota_per_tenant` is the flat fallback for
  a plan nobody has mapped yet.
* **Concurrency** is not. Three jobs already in flight is a "wait twenty seconds"
  condition, not a reason to sell anyone anything, so it is a 429 with
  `retry_after_seconds`. Returning 402 here would show a paywall to a firm that is
  already inside its plan and only has to wait — and no upgrade would clear it.

The estimate is what the app puts under its spinner, so it is per job type: a summary
of a 40-page scan and a one-clause risk review do not deserve the same countdown.
"""

import datetime as dt
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import envelope, security
from app.core.config import get_settings
from app.models import AiJob, Tenant

settings = get_settings()

# B.14 plan limits. Hard-coded per plan until the billing module owns them.
DAILY_JOB_LIMITS = {"solo": 20, "firm": 200, "enterprise": 2000}

ESTIMATE_SECONDS = {"summarize": 45, "research": 30, "draft": 60, "risk_review": 60}

TIMEOUT_SECONDS = {
    "summarize": settings.ai_summarize_timeout_seconds,
    "research": settings.ai_research_timeout_seconds,
    "draft": settings.ai_draft_timeout_seconds,
    "risk_review": settings.ai_risk_review_timeout_seconds,
}

IN_FLIGHT_STATUSES = ("queued", "running")

# Long enough that the queue has actually drained, short enough that the app's retry
# still feels like part of the same interaction.
CONCURRENCY_RETRY_AFTER_SECONDS = 20


def estimate_for(job_type: str) -> int:
    return ESTIMATE_SECONDS.get(job_type, 60)


def timeout_for(job_type: str) -> int:
    return TIMEOUT_SECONDS.get(job_type, settings.ai_research_timeout_seconds)


def in_flight_window_seconds() -> int:
    """How long a job may sit in `queued`/`running` before the concurrency cap stops
    believing it.

    A worker killed mid-job leaves its row `running` forever. Without this window
    three such rows would lock a firm out of the AI surface permanently, and with no
    failure anyone could see, because nothing crashed.
    """
    return max(TIMEOUT_SECONDS.values())


async def _enforce_concurrency(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    since = dt.datetime.now(dt.UTC) - dt.timedelta(seconds=in_flight_window_seconds())

    in_flight = await session.scalar(
        select(func.count())
        .select_from(AiJob)
        .where(AiJob.tenant_id == tenant_id)
        .where(AiJob.status.in_(IN_FLIGHT_STATUSES))
        .where(AiJob.created_at >= since)
    )

    if (in_flight or 0) >= settings.ai_max_concurrent_jobs_per_tenant:
        raise envelope.rate_limited(
            "Your firm already has several AI jobs running. Please try again shortly.",
            CONCURRENCY_RETRY_AFTER_SECONDS,
        )


async def _enforce_daily_quota(session: AsyncSession, tenant_id: uuid.UUID, plan: str) -> None:
    limit = DAILY_JOB_LIMITS.get(plan, settings.ai_daily_job_quota_per_tenant)
    since = dt.datetime.now(dt.UTC) - dt.timedelta(days=1)

    used = await session.scalar(
        select(func.count())
        .select_from(AiJob)
        .where(AiJob.tenant_id == tenant_id)
        .where(AiJob.created_at >= since)
    )

    if (used or 0) >= limit:
        upgrade_to = "firm" if plan == "solo" else "enterprise"
        raise envelope.quota_exceeded(
            f"You have used all {limit} AI requests for today.",
            limit=limit,
            plan=plan,
            upgrade_to=upgrade_to,
        )


async def create_job(
    session: AsyncSession,
    principal: security.Principal,
    job_type: str,
    payload: dict,
    *,
    conversation_id: uuid.UUID | None = None,
) -> AiJob:
    """Admits the job and persists it as `queued`. Never waits for it to run."""
    tenant = await session.get(Tenant, principal.tenant_id)

    # Concurrency first: it is the cheaper check and the recoverable one, so a firm
    # that is merely busy is told to wait rather than shown a paywall it cannot use.
    await _enforce_concurrency(session, principal.tenant_id)
    await _enforce_daily_quota(session, principal.tenant_id, tenant.plan if tenant else "solo")

    job = AiJob(
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        type=job_type,
        status="queued",
        input=payload,
        estimated_seconds=estimate_for(job_type),
        conversation_id=conversation_id,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job
