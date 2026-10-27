"""
Scheduled billing jobs:
  - Plan C.11.3: flip sent -> overdue past due_date, then polite
    reminders (max 3, spaced 5 days).
  - Plan C.11.6: cycle-end downgrade for cancelled subscriptions.
Same asyncio-in-Celery + per-tenant RLS pattern as the other workers.
"""

import asyncio

from sqlalchemy import select

from app.config import get_settings
from app.core.logging import get_logger
from app.core.security import utcnow
from app.db.enums import InvoiceStatus, NotificationType
from app.db.rls import set_tenant
from app.db.session import AsyncSessionLocal
from app.models.client import Client
from app.models.invoice import Invoice
from app.models.tenant import Tenant
from app.services.notification_dispatch_service import notify
from app.services.subscription_service import downgrade_expired_cancellations
from app.workers.celery_app import celery_app

logger = get_logger(__name__)
settings = get_settings()


def reminder_due(*, reminder_count: int, last_reminder_at, now) -> bool:
    """Max N reminders, spaced at least M days apart (plan C.11.3)."""
    if reminder_count >= settings.invoice_overdue_reminder_max_count:
        return False
    if last_reminder_at is not None and (now - last_reminder_at).days < settings.invoice_overdue_reminder_spacing_days:
        return False
    return True


async def _run_overdue_and_reminders() -> dict:
    stats = {"flipped_overdue": 0, "reminders_sent": 0}
    now = utcnow()

    async with AsyncSessionLocal() as session:
        tenants = list((await session.execute(select(Tenant))).scalars().all())

    for tenant in tenants:
        async with AsyncSessionLocal() as session:
            await set_tenant(session, str(tenant.id))

            sent = await session.execute(
                select(Invoice)
                .where(Invoice.status == InvoiceStatus.SENT)
                .where(Invoice.due_date.is_not(None))
                .where(Invoice.due_date < now.date())
            )
            for invoice in sent.scalars().all():
                invoice.status = InvoiceStatus.OVERDUE
                stats["flipped_overdue"] += 1
            await session.commit()

            overdue = await session.execute(select(Invoice).where(Invoice.status == InvoiceStatus.OVERDUE))
            for invoice in overdue.scalars().all():
                if not reminder_due(
                    reminder_count=invoice.reminder_count, last_reminder_at=invoice.last_reminder_at, now=now
                ):
                    continue
                client = (
                    await session.execute(select(Client).where(Client.id == invoice.client_id))
                ).scalar_one_or_none()
                if client is None or not client.user_id:
                    continue

                await notify(
                    session,
                    tenant_id=tenant.id,
                    user_id=client.user_id,
                    type=NotificationType.PAYMENT_RECEIVED,  # no distinct "reminder" type in contract B.8
                    title=f"Payment reminder: Invoice {invoice.number}",
                    body=f"A friendly reminder that invoice {invoice.number} for "
                    f"Rs. {invoice.total_paise / 100:,.2f} is overdue.",
                    data={"invoice_id": str(invoice.id)},
                    channels={"push", "whatsapp", "sms"},
                    dedup_key=f"overdue_reminder:{invoice.id}:{invoice.reminder_count + 1}",
                )
                invoice.reminder_count += 1
                invoice.last_reminder_at = now
                stats["reminders_sent"] += 1
            await session.commit()

    return stats


async def _run_subscription_downgrades() -> dict:
    stats = {"downgraded": 0}
    async with AsyncSessionLocal() as session:
        tenants = list((await session.execute(select(Tenant))).scalars().all())
    for tenant in tenants:
        async with AsyncSessionLocal() as session:
            await set_tenant(session, str(tenant.id))
            stats["downgraded"] += await downgrade_expired_cancellations(session)
    return stats


@celery_app.task(name="app.workers.billing_worker.overdue_and_reminders")
def overdue_and_reminders():
    stats = asyncio.run(_run_overdue_and_reminders())
    logger.info("billing_overdue_and_reminders_done", **stats)
    return stats


@celery_app.task(name="app.workers.billing_worker.subscription_downgrades")
def subscription_downgrades():
    stats = asyncio.run(_run_subscription_downgrades())
    logger.info("billing_subscription_downgrades_done", **stats)
    return stats
