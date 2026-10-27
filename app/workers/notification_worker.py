"""
Scheduled notification jobs (plan C.10 point 2):

    "daily digest at user-configured time (default 19:00): 'Kal aapki
    N hearings hain -- [case list]'; morning-of reminder at 07:30;
    hearing-outcome nudge the evening after a hearing ('Update outcome
    for ...')."

Same asyncio-inside-sync-Celery-task + per-tenant RLS pattern as
app/workers/ecourts_worker.py. All sends go through
notification_dispatch_service.notify() with a dedup_key, so a retried
task (or a beat misfire) never double-sends -- plan C.10 DoD: "all
sends idempotent (no double digests on retry)".
"""

import asyncio
import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.logging import get_logger
from app.db.enums import NotificationType
from app.db.rls import set_tenant
from app.db.session import AsyncSessionLocal
from app.db.tenant import TenantContext
from app.models.case import Case
from app.models.case_assignee import CaseAssignee
from app.models.hearing import Hearing
from app.models.notification_settings import NotificationSettings
from app.models.tenant import Tenant
from app.models.user import User
from app.services.notification_dispatch_service import notify
from app.services.notification_templates import (
    daily_digest_copy,
    hearing_reminder_copy,
    outcome_nudge_copy,
)
from app.workers.celery_app import celery_app

logger = get_logger(__name__)
settings = get_settings()

IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))

# Only these roles get case-hearing notifications; clients use the
# separate portal experience (contract B.6 "Client mode").
STAFF_ROLES = ("firm_admin", "lawyer", "intern")


def _ist_now() -> datetime.datetime:
    return datetime.datetime.now(tz=IST)


async def _hearings_for_user_on_date(
    session: AsyncSession, *, user: User, date: datetime.date
) -> list[tuple[Hearing, Case]]:
    stmt = (
        select(Hearing, Case)
        .join(Case, Case.id == Hearing.case_id)
        .where(Hearing.date == date)
    )
    if user.role != "firm_admin":
        stmt = stmt.join(CaseAssignee, CaseAssignee.case_id == Case.id).where(
            CaseAssignee.user_id == user.id
        )
    result = await session.execute(stmt)
    return [(h, c) for h, c in result.all()]


async def _staff_users_with_settings(
    session: AsyncSession,
) -> list[tuple[User, NotificationSettings | None]]:
    result = await session.execute(
        select(User, NotificationSettings)
        .outerjoin(NotificationSettings, NotificationSettings.user_id == User.id)
        .where(User.role.in_(STAFF_ROLES))
    )
    return list(result.all())


def _digest_time_for(settings_row: NotificationSettings | None) -> datetime.time:
    if settings_row is not None:
        return settings_row.digest_time
    hh, mm = settings.notification_default_digest_time.split(":")
    return datetime.time(int(hh), int(mm))


def _push_enabled_for(settings_row: NotificationSettings | None) -> bool:
    return settings_row.push_enabled if settings_row is not None else True


async def _run_digest_scan() -> dict:
    """
    Runs every settings.notification_digest_scan_interval_minutes
    (celery beat schedule). For each staff user whose configured
    digest_time falls in the current scan window, sends tomorrow's
    hearing count as a daily_digest push.
    """
    now = _ist_now()
    window_minutes = settings.notification_digest_scan_interval_minutes
    current_bucket = (now.hour * 60 + now.minute) // window_minutes
    tomorrow = now.date() + datetime.timedelta(days=1)

    stats = {"sent": 0, "skipped_no_hearings": 0, "skipped_settings": 0}

    async with AsyncSessionLocal() as session:
        tenants = list((await session.execute(select(Tenant))).scalars().all())

    for tenant in tenants:
        async with AsyncSessionLocal() as session:
            await set_tenant(session, str(tenant.id))

            for user, settings_row in await _staff_users_with_settings(session):
                digest_time = _digest_time_for(settings_row)
                user_bucket = (digest_time.hour * 60 + digest_time.minute) // window_minutes

                if user_bucket != current_bucket or not _push_enabled_for(settings_row):
                    stats["skipped_settings"] += 1
                    continue

                hearings = await _hearings_for_user_on_date(session, user=user, date=tomorrow)
                if not hearings:
                    stats["skipped_no_hearings"] += 1
                    continue

                title, body = daily_digest_copy(
                    hearing_count=len(hearings), language=user.language
                )
                sent = await notify(
                    session,
                    tenant_id=tenant.id,
                    user_id=user.id,
                    type=NotificationType.DAILY_DIGEST,
                    title=title,
                    body=body,
                    data={"date": tomorrow.isoformat(), "hearing_count": len(hearings)},
                    channels={"push", "whatsapp", "sms"},
                    dedup_key=f"digest:{tomorrow.isoformat()}",
                )
                if sent is not None:
                    stats["sent"] += 1

    return stats


async def _run_morning_reminders() -> dict:
    """Fixed 07:30 IST: one hearing_reminder push per hearing scheduled today."""
    today = _ist_now().date()
    stats = {"sent": 0}

    async with AsyncSessionLocal() as session:
        tenants = list((await session.execute(select(Tenant))).scalars().all())

    for tenant in tenants:
        async with AsyncSessionLocal() as session:
            await set_tenant(session, str(tenant.id))

            for user, settings_row in await _staff_users_with_settings(session):
                if not _push_enabled_for(settings_row):
                    continue

                for hearing, case in await _hearings_for_user_on_date(
                    session, user=user, date=today
                ):
                    title, body = hearing_reminder_copy(
                        case_title=case.title,
                        hearing_date=today.isoformat(),
                        language=user.language,
                    )
                    sent = await notify(
                        session,
                        tenant_id=tenant.id,
                        user_id=user.id,
                        type=NotificationType.HEARING_REMINDER,
                        title=title,
                        body=body,
                        data={
                            "case_id": str(case.id),
                            "hearing_id": str(hearing.id),
                            "hearing_date": today.isoformat(),
                        },
                        channels={"push", "whatsapp", "sms"},
                        dedup_key=f"hearing_reminder:{hearing.id}:{today.isoformat()}",
                    )
                    if sent is not None:
                        stats["sent"] += 1

    return stats


async def _run_outcome_nudges() -> dict:
    """
    Evening after a hearing (default 20:00 IST): nudges assignees of
    today's hearings that don't yet have outcome_notes recorded.
    Reuses the "hearing_reminder" push type with a payload marker,
    since contract B.8's fixed type list doesn't have a distinct
    "outcome nudge" type (see notification_templates.outcome_nudge_copy).
    """
    today = _ist_now().date()
    stats = {"sent": 0}

    async with AsyncSessionLocal() as session:
        tenants = list((await session.execute(select(Tenant))).scalars().all())

    for tenant in tenants:
        async with AsyncSessionLocal() as session:
            await set_tenant(session, str(tenant.id))

            stmt = (
                select(Hearing, Case)
                .join(Case, Case.id == Hearing.case_id)
                .where(Hearing.date == today)
                .where(Hearing.outcome_notes.is_(None))
            )
            hearings_today = list((await session.execute(stmt)).all())
            if not hearings_today:
                continue

            for hearing, case in hearings_today:
                assignees_result = await session.execute(
                    select(User)
                    .join(CaseAssignee, CaseAssignee.user_id == User.id)
                    .where(CaseAssignee.case_id == case.id)
                    .where(User.role.in_(STAFF_ROLES))
                )
                for user in assignees_result.scalars().all():
                    title, body = outcome_nudge_copy(
                        case_title=case.title, language=user.language
                    )
                    sent = await notify(
                        session,
                        tenant_id=tenant.id,
                        user_id=user.id,
                        type=NotificationType.HEARING_REMINDER,
                        title=title,
                        body=body,
                        data={
                            "case_id": str(case.id),
                            "hearing_id": str(hearing.id),
                            "reminder_kind": "outcome_nudge",
                        },
                        channels={"push"},
                        dedup_key=f"outcome_nudge:{hearing.id}",
                    )
                    if sent is not None:
                        stats["sent"] += 1

    return stats


@celery_app.task(name="app.workers.notification_worker.digest_scan")
def digest_scan():
    stats = asyncio.run(_run_digest_scan())
    logger.info("notification_digest_scan_done", **stats)
    return stats


@celery_app.task(name="app.workers.notification_worker.morning_reminders")
def morning_reminders():
    stats = asyncio.run(_run_morning_reminders())
    logger.info("notification_morning_reminders_done", **stats)
    return stats


@celery_app.task(name="app.workers.notification_worker.outcome_nudges")
def outcome_nudges():
    stats = asyncio.run(_run_outcome_nudges())
    logger.info("notification_outcome_nudges_done", **stats)
    return stats
