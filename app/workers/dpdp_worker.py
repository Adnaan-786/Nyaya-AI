"""
DPDP background jobs (plan C.12.2): data export and, once the 30-day
soft window has elapsed, hard deletion. Same asyncio-in-Celery +
per-tenant RLS pattern as the other workers.
"""

import asyncio
from uuid import UUID

import sentry_sdk
from sqlalchemy import select

from app.core.logging import get_logger
from app.core.security import utcnow
from app.db.rls import set_tenant
from app.db.session import AsyncSessionLocal
from app.models.data_request import DataRequest
from app.models.tenant import Tenant
from app.services import dpdp_service
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


def dispatch_export(request_id: UUID, tenant_id: UUID) -> None:
    """
    Best-effort enqueue. If the broker is down the request simply stays
    `pending` and the periodic sweep (process_pending_exports) picks it
    up, so an export request is never lost -- and the API call never
    hangs on a dead broker.
    """
    try:
        run_export_task.apply_async((str(request_id), str(tenant_id)), retry=False)
    except Exception as exc:  # noqa: BLE001
        logger.warning("export_enqueue_failed_will_be_swept", request_id=str(request_id), error=str(exc))


async def _export_one(request_id: UUID, tenant_id: UUID) -> str:
    async with AsyncSessionLocal() as session:
        await set_tenant(session, str(tenant_id))
        request = (
            await session.execute(select(DataRequest).where(DataRequest.id == request_id))
        ).scalar_one_or_none()
        if request is None or request.kind != "export" or request.status not in ("pending", "processing"):
            return "skipped"
        try:
            await dpdp_service.run_export(session, request)
            return "completed"
        except Exception as exc:  # noqa: BLE001
            await session.rollback()
            request = (
                await session.execute(select(DataRequest).where(DataRequest.id == request_id))
            ).scalar_one()
            request.status = "failed"
            request.error = str(exc)[:1000]
            await session.commit()
            sentry_sdk.capture_exception(exc)
            logger.exception("dpdp_export_failed", request_id=str(request_id))
            return "failed"


async def _sweep_pending_exports() -> dict:
    stats = {"completed": 0, "failed": 0, "skipped": 0}
    async with AsyncSessionLocal() as session:
        tenants = list((await session.execute(select(Tenant.id))).scalars().all())
    for tenant_id in tenants:
        async with AsyncSessionLocal() as session:
            await set_tenant(session, str(tenant_id))
            ids = list(
                (
                    await session.execute(
                        select(DataRequest.id).where(DataRequest.kind == "export").where(DataRequest.status == "pending")
                    )
                ).scalars().all()
            )
        for request_id in ids:
            stats[await _export_one(request_id, tenant_id)] += 1
    return stats


async def _process_due_deletions() -> dict:
    stats = {"deleted": 0, "failed": 0}
    now = utcnow()
    async with AsyncSessionLocal() as session:
        tenants = list((await session.execute(select(Tenant.id))).scalars().all())
    for tenant_id in tenants:
        async with AsyncSessionLocal() as session:
            await set_tenant(session, str(tenant_id))
            due = list(
                (
                    await session.execute(
                        select(DataRequest)
                        .where(DataRequest.kind == "delete")
                        .where(DataRequest.status == "pending")
                        .where(DataRequest.scheduled_for <= now)
                    )
                ).scalars().all()
            )
            due_ids = [r.id for r in due]
            for request_id in due_ids:
                try:
                    request = (
                        await session.execute(select(DataRequest).where(DataRequest.id == request_id))
                    ).scalar_one()
                    await dpdp_service.run_hard_delete(session, request)
                    stats["deleted"] += 1
                except Exception as exc:  # noqa: BLE001 - one bad request must not block the rest
                    await session.rollback()
                    stats["failed"] += 1
                    sentry_sdk.capture_exception(exc)
                    logger.error("dpdp_hard_delete_failed", request_id=str(request_id), error=str(exc))
                    # Put it back in the queue (it was marked "processing") so tomorrow's
                    # run retries it, instead of stranding it.
                    failed = (
                        await session.execute(select(DataRequest).where(DataRequest.id == request_id))
                    ).scalar_one()
                    failed.status = "pending"
                    failed.error = str(exc)[:1000]
                    await session.commit()
    return stats


@celery_app.task(name="app.workers.dpdp_worker.run_export_task")
def run_export_task(request_id: str, tenant_id: str):
    return asyncio.run(_export_one(UUID(request_id), UUID(tenant_id)))


@celery_app.task(name="app.workers.dpdp_worker.process_pending_exports")
def process_pending_exports():
    stats = asyncio.run(_sweep_pending_exports())
    logger.info("dpdp_pending_exports_done", **stats)
    return stats


@celery_app.task(name="app.workers.dpdp_worker.process_due_deletions")
def process_due_deletions():
    stats = asyncio.run(_process_due_deletions())
    logger.info("dpdp_due_deletions_done", **stats)
    return stats
