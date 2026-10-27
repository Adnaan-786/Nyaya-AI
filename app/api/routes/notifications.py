from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AuthContext, get_current_auth, get_tenant_scoped_db
from app.core.responses import ApiResponse, Meta
from app.schemas.notification import (
    NotificationOut,
    NotificationSettingsOut,
    NotificationSettingsUpdateIn,
    NotificationsReadIn,
)
from app.services import notification_inbox_service, notification_settings_service

router = APIRouter(tags=["Notifications"])


@router.get("/notifications", response_model=ApiResponse[list[NotificationOut]])
async def list_notifications(
    unread_only: bool = False,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    auth: AuthContext = Depends(get_current_auth),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[list[NotificationOut]]:
    tenant = auth.as_tenant_context()
    notifications, total = await notification_inbox_service.list_notifications(
        session,
        tenant,
        auth.user_id,
        unread_only=unread_only,
        limit=limit,
        offset=(page - 1) * limit,
    )
    return ApiResponse(
        success=True,
        data=[NotificationOut.model_validate(n) for n in notifications],
        meta=Meta(page=page, limit=limit, total=total),
    )


@router.post("/notifications/read", response_model=ApiResponse[dict])
async def mark_notifications_read(
    payload: NotificationsReadIn,
    auth: AuthContext = Depends(get_current_auth),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[dict]:
    tenant = auth.as_tenant_context()
    count = await notification_inbox_service.mark_read(
        session, tenant, auth.user_id, ids=payload.ids
    )
    return ApiResponse(success=True, data={"marked_read": count})


@router.get("/notification-settings", response_model=ApiResponse[NotificationSettingsOut])
async def get_notification_settings(
    auth: AuthContext = Depends(get_current_auth),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[NotificationSettingsOut]:
    settings_row = await notification_settings_service.get_or_create_settings(
        session, auth.user_id
    )
    return ApiResponse(success=True, data=NotificationSettingsOut.model_validate(settings_row))


@router.patch("/notification-settings", response_model=ApiResponse[NotificationSettingsOut])
async def update_notification_settings(
    payload: NotificationSettingsUpdateIn,
    auth: AuthContext = Depends(get_current_auth),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[NotificationSettingsOut]:
    settings_row = await notification_settings_service.get_or_create_settings(
        session, auth.user_id
    )
    settings_row = await notification_settings_service.update_settings(
        session,
        settings_row,
        digest_time=payload.digest_time,
        push_enabled=payload.push_enabled,
        whatsapp_enabled=payload.whatsapp_enabled,
        sms_enabled=payload.sms_enabled,
    )
    return ApiResponse(success=True, data=NotificationSettingsOut.model_validate(settings_row))
