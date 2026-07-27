"""Hearing reminders (B.8 `hearing_reminder`) — the push IC-1 is defined by.

Run from cron, one hour apart:

    ./.venv/bin/python -m scripts.send_reminders

Two properties matter more than the scheduling itself:

**Idempotence.** A reminder already sent for a hearing is never sent again, tracked by a
Notification row rather than by trusting the scheduler to fire exactly once. Cron
overlapping, a retry, or a redeploy mid-run would otherwise wake a lawyer twice at 6 am.

**IST.** "Tomorrow" is tomorrow *in India*. Computing it from the server's clock sends
the wrong day's list for five and a half hours every night on a UTC host.
"""

import datetime as dt
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.india import today_in_india
from app.integrations import fcm
from app.models import Case, CaseAssignee, Hearing, Notification, User

logger = logging.getLogger(__name__)

# D.6: the evening before is when a lawyer can still prepare. A reminder at 9 am for a
# 10:30 hearing is an alarm, not a reminder.
REMIND_DAYS_AHEAD = 1


async def send_hearing_reminders(session: AsyncSession) -> int:
    """Sends one reminder per assigned lawyer per hearing listed tomorrow."""
    target = dt.date.fromordinal(today_in_india().toordinal() + REMIND_DAYS_AHEAD)

    rows = (
        await session.execute(
            select(Hearing, Case)
            .join(Case, Case.id == Hearing.case_id)
            .where(Hearing.date == target)
        )
    ).all()

    sent = 0
    for hearing, case in rows:
        for user in await _recipients(session, case):
            if await _already_notified(session, user.id, hearing.id):
                continue

            when = hearing.time.strftime("%I:%M %p").lstrip("0") if hearing.time else None
            body = ", ".join(
                filter(
                    None,
                    [case.title, when, hearing.courtroom or case.court_name],
                )
            )

            await fcm.send_to_user(
                session,
                user_id=user.id,
                tenant_id=case.tenant_id,
                push_type=fcm.HEARING_REMINDER,
                title="Hearing tomorrow",
                body=body,
                deep_link=f"nyayaai://case/{case.id}",
            )
            # Stamped with the hearing id so the idempotence check above can find it.
            await _stamp(session, user.id, case.tenant_id, hearing.id)
            sent += 1

    await session.commit()
    logger.info("sent %d hearing reminders for %s", sent, target)
    return sent


async def _recipients(session: AsyncSession, case: Case) -> list[User]:
    """Assigned lawyers, or the whole firm's staff when nobody is assigned.

    Falling back to everyone is deliberate: an unassigned hearing that reminds nobody is
    exactly the case this feature exists to prevent.
    """
    assigned = (
        await session.scalars(
            select(User)
            .join(CaseAssignee, CaseAssignee.user_id == User.id)
            .where(CaseAssignee.case_id == case.id)
        )
    ).all()

    if assigned:
        return list(assigned)

    return list(
        (
            await session.scalars(
                select(User).where(User.tenant_id == case.tenant_id, User.role != "client")
            )
        ).all()
    )


async def _already_notified(session: AsyncSession, user_id, hearing_id) -> bool:
    existing = await session.scalar(
        select(Notification.id).where(
            Notification.user_id == user_id,
            Notification.type == fcm.HEARING_REMINDER,
            Notification.payload["hearing_id"].astext == str(hearing_id),
        )
    )
    return existing is not None


async def _stamp(session: AsyncSession, user_id, tenant_id, hearing_id) -> None:
    """Records which hearing the just-created notification was for.

    `send_to_user` writes the row without a payload; this attaches the hearing id to the
    newest one so a re-run can recognise it.
    """
    newest = (
        await session.scalars(
            select(Notification)
            .where(Notification.user_id == user_id, Notification.type == fcm.HEARING_REMINDER)
            .order_by(Notification.created_at.desc())
            .limit(1)
        )
    ).first()

    if newest is not None:
        newest.payload = {"hearing_id": str(hearing_id)}
    else:
        session.add(
            Notification(
                tenant_id=tenant_id,
                user_id=user_id,
                type=fcm.HEARING_REMINDER,
                title="Hearing tomorrow",
                body="",
                payload={"hearing_id": str(hearing_id)},
            )
        )
