"""Team-management schemas (B.4 roles, firm-admin only writes)."""

import datetime as dt
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    # Optional for the same reason as the auth schema's UserOut: a colleague who signed
    # up through the email OTP channel has no phone, and requiring one here 500s the
    # whole team roster the moment one such member joins the firm.
    phone: str | None = None
    email: str | None = None
    role: str
    language: str
    created_at: dt.datetime


class UserRoleUpdate(BaseModel):
    # Never "client": that role is a portal login created by /clients/{id}/invite,
    # not something a firm-admin hands out through team management.
    role: Literal["firm_admin", "lawyer", "intern"]
