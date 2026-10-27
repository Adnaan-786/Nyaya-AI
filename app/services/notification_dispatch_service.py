from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.enums import NotificationType
from app.integrations import fcm, whatsapp
from app.integrations.msg91 import send_sms
from app.models.device import Device
from app.models.notification import Notification
from app.models.user import User
from app.services.notification_settings_service import get_or_create_settings
from app.services.notification_templates import deep_link_for

logger = get_logger(__name__)


async def _already_sent_today(
    session: AsyncSession, *, user_id: UUID, notification_type: NotificationType, dedup_key: str
) -> bool:
    """
    Plan C.10 DoD: "all sends idempotent (no double digests on retry)".
    Scheduled jobs (digest/reminder/nudge) pass a dedup_key derived
    from the date (and hearing_id, where relevant); a retry that finds
    a matching notification already recorded skips re-sending.
    """
    result = await session.execute(
        select(Notification.id)
        .where(Notification.user_id == user_id)
        .where(Notification.type == notification_type)
        .where(Notification.payload.op("->>")("dedup_key") == dedup_key)
    )
    return result.scalar_one_or_none() is not None


async def notify(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
    type: NotificationType,
    title: str,
    body: str,
    data: dict,
    channels: set[str] | None = None,
    dedup_key: str | None = None,
) -> Notification | None:
    """
    Single entry point for every notification in the system (plan
    C.10). Always writes the in-app inbox row; then attempts delivery
    over `channels` (subset of {"push", "whatsapp", "sms"}), respecting
    the user's notification_settings opt-outs -- "unsubscribed users
    never messaged" (plan C.10 DoD).

    Returns None (no-op) if `dedup_key` matches an already-sent
    notification, so callers can safely retry without double-sending.
    """
    channels = channels or {"push"}

    # Contract B.8: every push carries {type, title, body, deep_link}
    # plus type-specific data. Computed here so no caller can forget it.
    type_str = type.value if isinstance(type, NotificationType) else type
    deep_link = deep_link_for(type_str, data)
    fcm_data = {**data, "type": type_str, "deep_link": deep_link}

    if dedup_key is not None and await _already_sent_today(
        session, user_id=user_id, notification_type=type, dedup_key=dedup_key
    ):
        logger.info("notification_deduped", user_id=str(user_id), type=type, dedup_key=dedup_key)
        return None

    stored_payload = dict(data)
    stored_payload["deep_link"] = deep_link
    if dedup_key is not None:
        stored_payload["dedup_key"] = dedup_key

    notification = Notification(
        tenant_id=tenant_id, user_id=user_id, type=type, payload=stored_payload
    )
    session.add(notification)
    await session.commit()

    user_result = await session.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if user is None:
        return notification

    settings_row = await get_or_create_settings(session, user_id)

    if "push" in channels and settings_row.push_enabled:
        devices_result = await session.execute(
            select(Device).where(Device.user_id == user_id)
        )
        tokens = [d.fcm_token for d in devices_result.scalars().all()]
        if tokens:
            try:
                invalid_tokens = await fcm.send_push(tokens, title=title, body=body, data=fcm_data)
                if invalid_tokens:
                    await session.execute(
                        delete(Device).where(Device.fcm_token.in_(invalid_tokens))
                    )
                    await session.commit()
            except NotImplementedError:
                logger.info("fcm_push_skipped_not_configured")

    whatsapp_sent = False
    if "whatsapp" in channels and settings_row.whatsapp_enabled and user.phone:
        try:
            whatsapp_sent = await whatsapp.send_whatsapp_template(
                user.phone, notification_type=type.value, params=[body]
            )
        except NotImplementedError:
            logger.info("whatsapp_send_skipped_not_configured")

    if "sms" in channels and settings_row.sms_enabled and user.phone and not whatsapp_sent:
        try:
            await send_sms(user.phone, body)
        except NotImplementedError:
            logger.info("sms_send_skipped_not_configured")

    return notification
