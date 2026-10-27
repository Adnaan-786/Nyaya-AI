from datetime import time
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.notification_settings import NotificationSettings

settings = get_settings()


def _default_digest_time() -> time:
    hh, mm = settings.notification_default_digest_time.split(":")
    return time(int(hh), int(mm))


async def get_or_create_settings(session: AsyncSession, user_id: UUID) -> NotificationSettings:
    result = await session.execute(
        select(NotificationSettings).where(NotificationSettings.user_id == user_id)
    )
    row = result.scalar_one_or_none()
    if row is not None:
        return row

    row = NotificationSettings(user_id=user_id, digest_time=_default_digest_time())
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def update_settings(
    session: AsyncSession,
    row: NotificationSettings,
    *,
    digest_time: time | None = None,
    push_enabled: bool | None = None,
    whatsapp_enabled: bool | None = None,
    sms_enabled: bool | None = None,
) -> NotificationSettings:
    if digest_time is not None:
        row.digest_time = digest_time
    if push_enabled is not None:
        row.push_enabled = push_enabled
    if whatsapp_enabled is not None:
        row.whatsapp_enabled = whatsapp_enabled
    if sms_enabled is not None:
        row.sms_enabled = sms_enabled

    await session.commit()
    await session.refresh(row)
    return row
