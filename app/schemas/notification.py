from datetime import datetime, time
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    type: str
    payload: dict[str, Any]
    read_at: datetime | None = None
    created_at: datetime


class NotificationsReadIn(BaseModel):
    """POST /notifications/read. Omit ids to mark every unread notification as read."""

    ids: list[UUID] | None = None


class NotificationSettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    digest_time: time
    push_enabled: bool
    whatsapp_enabled: bool
    sms_enabled: bool


class NotificationSettingsUpdateIn(BaseModel):
    digest_time: time | None = None
    push_enabled: bool | None = None
    whatsapp_enabled: bool | None = None
    sms_enabled: bool | None = None
