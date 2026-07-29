import uuid

import pytest
import random
from app.db.repository import Repository
from app.db.rls import set_tenant
from app.db.session import AsyncSessionLocal
from app.db.tenant import TenantContext
from app.models.tenant import Tenant
from app.models.user import User


@pytest.mark.asyncio
async def test_repository_get_is_tenant_scoped(db_session):
    tenant_a = Tenant(id=uuid.uuid4(), name="Firm A", plan="free")
    tenant_b = Tenant(id=uuid.uuid4(), name="Firm B", plan="free")

    db_session.add_all([tenant_a, tenant_b])
    await db_session.flush()

    user_a = User(
        tenant_id=tenant_a.id,
        phone=str(random.randint(6000000000, 9999999999)),
        name="Alice",
        email="alice@test.com",
        role="admin",
        language="en",
    )

    db_session.add(user_a)
    await db_session.flush()
    await db_session.refresh(user_a)

    repo = Repository(db_session, TenantContext(tenant_a.id, user_a.id), User)
    assert await repo.exists(user_a.id)
