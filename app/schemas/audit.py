from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    actor_id: UUID | None = None
    action: str
    entity_type: str
    entity_id: str | None = None
    ip: str | None = None
    at: datetime
