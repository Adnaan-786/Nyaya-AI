"""
Retention jobs (plan C.12.4):

    OTP rows 24 h, audit 3 years, documents until a deletion request;
    logs 90 days (that one is CloudWatch/log-driver configuration, see
    docs/runbooks/data-retention.md -- it is not something the app can
    enforce from inside).

Also: the 60-day stale push-token sweep promised in plan C.5.5, expiry of
finished export archives, and keeping the monthly audit partitions
rolling forward.
"""

import asyncio
import datetime

from sqlalchemy import delete, select, text

from app.core.logging import get_logger
from app.core.security import utcnow
from app.db.rls import set_tenant
from app.db.session import AsyncSessionLocal
from app.integrations import storage
from app.models.data_request import DataRequest
from app.models.device import Device
from app.models.otp_request import OTPRequest
from app.models.refresh_token import RefreshToken
from app.models.tenant import Tenant
from app.workers.celery_app import celery_app

logger = get_logger(__name__)

OTP_RETENTION = datetime.timedelta(hours=24)
STALE_DEVICE_AFTER = datetime.timedelta(days=60)
EXPIRED_REFRESH_TOKEN_GRACE = datetime.timedelta(days=7)
AUDIT_RETENTION_MONTHS = 36
AUDIT_PARTITIONS_AHEAD = 3


async def _purge_expired() -> dict:
    now = utcnow()
    stats = {"otp_rows": 0, "stale_devices": 0, "refresh_tokens": 0, "exports_expired": 0, "audit_partitions_dropped": 0}

    async with AsyncSessionLocal() as session:
        stats["otp_rows"] = (await session.execute(delete(OTPRequest).where(OTPRequest.updated_at < now - OTP_RETENTION))).rowcount or 0
        stats["stale_devices"] = (await session.execute(delete(Device).where(Device.updated_at < now - STALE_DEVICE_AFTER))).rowcount or 0
        stats["refresh_tokens"] = (
            await session.execute(delete(RefreshToken).where(RefreshToken.expires_at < now - EXPIRED_REFRESH_TOKEN_GRACE))
        ).rowcount or 0
        await session.commit()

        stats["audit_partitions_dropped"] = (
            await session.execute(
                text("SELECT audit_drop_partitions_before((date_trunc('month', now()) - make_interval(months => :m))::date)"),
                {"m": AUDIT_RETENTION_MONTHS},
            )
        ).scalar_one()
        await session.commit()

        tenants = list((await session.execute(select(Tenant.id))).scalars().all())

    for tenant_id in tenants:
        async with AsyncSessionLocal() as session:
            await set_tenant(session, str(tenant_id))
            expired = list(
                (
                    await session.execute(
                        select(DataRequest)
                        .where(DataRequest.kind == "export")
                        .where(DataRequest.status == "completed")
                        .where(DataRequest.expires_at < now)
                    )
                ).scalars().all()
            )
            for request in expired:
                if request.result_key:
                    try:
                        storage.delete_object(request.result_key)
                    except Exception as exc:  # noqa: BLE001
                        logger.error("export_delete_failed", request_id=str(request.id), error=str(exc))
                request.status = "expired"
                request.result_key = None
                stats["exports_expired"] += 1
            await session.commit()

    return stats


async def _ensure_audit_partitions() -> int:
    async with AsyncSessionLocal() as session:
        for offset in range(0, AUDIT_PARTITIONS_AHEAD + 1):
            await session.execute(
                text("SELECT audit_create_partition((date_trunc('month', now()) + make_interval(months => :o))::date)"),
                {"o": offset},
            )
        await session.commit()
    return AUDIT_PARTITIONS_AHEAD + 1


@celery_app.task(name="app.workers.retention_worker.purge_expired")
def purge_expired():
    stats = asyncio.run(_purge_expired())
    logger.info("retention_purge_done", **stats)
    return stats


@celery_app.task(name="app.workers.retention_worker.ensure_audit_partitions")
def ensure_audit_partitions():
    return asyncio.run(_ensure_audit_partitions())
