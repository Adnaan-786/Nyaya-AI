from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID

JsonType = JSONB
UUIDType = UUID(as_uuid=True)