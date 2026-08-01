"""
Scheduled eCourts sync polling (plan C.7 point 3):

    "every synced case refreshed on a schedule: daily at 06:00 IST
    baseline; cases with a hearing today re-checked at 14:00 and 19:00
    IST (orders/next dates appear in the evening). Batch requests;
    respect provider rate limits with a token bucket; exponential
    backoff on failures; alert if a case fails 3 consecutive days."

The actual cron schedule lives in app/workers/celery_app.py. These
tasks are plain sync functions (Celery's default) that drive the async
service layer via asyncio.run, one tenant at a time so Postgres RLS
sees the right `app.tenant_id` for every query.
"""

import asyncio
import datetime

from sqlalchemy import select

from app.config import get_settings
from app.core.exceptions import AppException
from app.core.logging import get_logger
from app.core.rate_limiter import TokenBucket
from app.core.security import utcnow
from app.db.rls import set_tenant
from app.db.session import AsyncSessionLocal
from app.db.tenant import TenantContext
from app.integrations.ecourts import ECourtsProviderError
from app.models.case import Case
from app.models.tenant import Tenant
from app.services.ecourts_service import _apply_sync
from app.workers.celery_app import celery_app

logger = get_logger(__name__)
settings = get_settings()

# Conservative default: 1 lookup/sec, burst of 5. Commercial eCourts
# APIs bill per lookup (plan C.7 point 5), so pacing also protects cost.
_bucket = TokenBucket(rate=1.0, capacity=5)


async def _sync_cases_matching(*, hearing_today_only: bool) -> dict:
    """Runs one polling pass across every tenant's synced cases."""

    stats = {"synced": 0, "failed": 0, "skipped": 0}

    async with AsyncSessionLocal() as session:
        tenants = list((await session.execute(select(Tenant))).scalars().all())

    for tenant in tenants:
        # user_id is unused by _apply_sync (only tenant_id is read, to
        # stamp notifications); there's no "current user" in a
        # background job, so this is a system-context placeholder.
        tenant_ctx = TenantContext(tenant_id=tenant.id, user_id=tenant.id)

        async with AsyncSessionLocal() as session:
            await set_tenant(session, str(tenant.id))

            stmt = select(Case).where(Case.ecourts_synced.is_(True)).where(
                Case.status != "archived"
            )
            if hearing_today_only:
                today = utcnow().date()
                stmt = stmt.where(Case.next_hearing_date == today)

            cases = list((await session.execute(stmt)).scalars().all())

            for case in cases:
                await _bucket.acquire()
                try:
                    await _apply_sync(session, tenant_ctx, case)
                    stats["synced"] += 1
                except (ECourtsProviderError, AppException) as exc:
                    stats["failed"] += 1
                    logger.warning(
                        "ecourts_sync_case_failed",
                        case_id=str(case.id),
                        tenant_id=str(tenant.id),
                        error=str(exc),
                    )
                except Exception:  # noqa: BLE001 - never let one bad case kill the batch
                    stats["failed"] += 1
                    logger.exception(
                        "ecourts_sync_case_unexpected_error",
                        case_id=str(case.id),
                        tenant_id=str(tenant.id),
                    )

    return stats


@celery_app.task(name="app.workers.ecourts_worker.sync_all_cases", bind=True, max_retries=3)
def sync_all_cases(self):
    """Daily 06:00 IST baseline refresh of every synced case, every tenant."""
    try:
        stats = asyncio.run(_sync_cases_matching(hearing_today_only=False))
        logger.info("ecourts_sync_all_cases_done", **stats)
        return stats
    except Exception as exc:  # noqa: BLE001
        # Exponential backoff on unexpected batch-level failure (plan C.7 pt 3).
        raise self.retry(exc=exc, countdown=2**self.request.retries * 60)


@celery_app.task(
    name="app.workers.ecourts_worker.sync_hearing_today_cases", bind=True, max_retries=3
)
def sync_hearing_today_cases(self):
    """14:00 and 19:00 IST re-check for cases with a hearing today."""
    try:
        stats = asyncio.run(_sync_cases_matching(hearing_today_only=True))
        logger.info("ecourts_sync_hearing_today_done", **stats)
        return stats
    except Exception as exc:  # noqa: BLE001
        raise self.retry(exc=exc, countdown=2**self.request.retries * 60)
