"""B.8 notification list/read schemas.

Field names mirror `Notification` (`app/models/entities.py`) exactly — the app's
notification inbox is a straight list-and-mark-read UI, so there is no derived data
here beyond what the row already carries.
"""

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: str
    title: str
    body: str
    deep_link: str | None = None
    payload: dict
    read_at: dt.datetime | None = None
    created_at: dt.datetime
