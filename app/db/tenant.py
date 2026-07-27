from dataclasses import dataclass
from uuid import UUID


@dataclass
class TenantContext:
    tenant_id: UUID
    user_id: UUID