from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import NotificationType
from app.models.notification import Notification


async def notify_user(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
    type: NotificationType,
    payload: dict,
) -> Notification:
    """
    Writes the in-app inbox row (GET /notifications, contract B.6).

    Full delivery -- FCM push (B.8), WhatsApp, SMS fallback -- is the
    M9 dispatcher's job (`notify(user, type, payload, channels)` per
    plan C.10). Callers from earlier modules (like M5's sync diff
    detection) can depend on this in-app write today and get push
    delivery "for free" once M9's dispatcher wraps it.
    """
    notification = Notification(
        tenant_id=tenant_id,
        user_id=user_id,
        type=type,
        payload=payload,
    )
    session.add(notification)
    # Caller controls the commit boundary (usually alongside the
    # mutation that triggered the notification).
    return notification
