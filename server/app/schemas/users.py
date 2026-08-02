"""Team-management schemas (B.4 roles, firm-admin only writes)."""

import datetime as dt
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    phone: str
    email: str | None = None
    role: str
    language: str
    created_at: dt.datetime


class UserRoleUpdate(BaseModel):
    # Never "client": that role is a portal login created by /clients/{id}/invite,
    # not something a firm-admin hands out through team management.
    role: Literal["firm_admin", "lawyer", "intern"]
