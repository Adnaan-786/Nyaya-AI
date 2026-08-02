"""B.8 notifications: list, mark-read, mark-all-read.

A notification belongs to one user, not the whole firm (hearing reminders, AI job
completion and payment alerts are all addressed to a specific `user_id`) — every
query here filters on `(tenant_id, user_id)` together, never `tenant_id` alone, or
one lawyer would see (and be able to mark read) a colleague's notifications.
"""

import datetime as dt
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Page, paginate
from app.core import envelope, security
from app.core.db import get_session, scoped
from app.models import Notification
from app.schemas.notifications import NotificationOut

router = APIRouter(tags=["notifications"])


@router.get("/notifications")
async def list_notifications(
    unread_only: bool = False,
    page: Page = Depends(),
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.require_staff),
):
    statement = scoped(Notification, principal.tenant_id).where(
        Notification.user_id == principal.user_id
    )
    if unread_only:
        statement = statement.where(Notification.read_at.is_(None))
    statement = statement.order_by(Notification.created_at.desc())

    rows, meta = await paginate(session, statement, page)
    return envelope.ok(
        [NotificationOut.model_validate(r).model_dump(mode="json") for r in rows], meta
    )


@router.patch("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.require_staff),
):
    # `get_scoped_or_404` only checks tenant_id — a notification is scoped one level
    # further, to the user it was addressed to, so that check is repeated by hand
    # here rather than trusting the tenant match alone.
    notification = await session.get(Notification, notification_id)
    if notification is None or notification.tenant_id != principal.tenant_id:
        raise envelope.not_found("notification")
    if notification.user_id != principal.user_id:
        raise envelope.not_found("notification")

    if notification.read_at is None:
        notification.read_at = dt.datetime.now(dt.UTC)
        await session.commit()
        await session.refresh(notification)
    # Already read: idempotent no-op, not an error — the app calls this on tap and
    # a double-tap must not surface a failure toast for something that already happened.

    return envelope.ok(NotificationOut.model_validate(notification).model_dump(mode="json"))


@router.post("/notifications/read-all")
async def mark_all_notifications_read(
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.require_staff),
):
    now = dt.datetime.now(dt.UTC)
    result = await session.execute(
        update(Notification)
        .where(
            Notification.tenant_id == principal.tenant_id,
            Notification.user_id == principal.user_id,
            Notification.read_at.is_(None),
        )
        .values(read_at=now)
    )
    await session.commit()
    return envelope.ok({"updated": result.rowcount or 0})
