import uuid

import pytest

from app.db.repository import Repository
from app.db.rls import set_tenant
from app.db.session import AsyncSessionLocal
from app.db.tenant import TenantContext
from app.models.tenant import Tenant
from app.models.user import User


@pytest.mark.asyncio
async def test_repository_get_is_tenant_scoped():

    async with AsyncSessionLocal() as session:

        tenant_a = Tenant(
            id=uuid.uuid4(),
            name="Firm A",
            plan="free",
        )

        tenant_b = Tenant(
            id=uuid.uuid4(),
            name="Firm B",
            plan="free",
        )

        session.add_all([tenant_a, tenant_b])
        await session.flush()

        user_a = User(
            tenant_id=tenant_a.id,
            phone="9000000001",
            name="Alice",
            email="alice@test.com",
            role="admin",
            language="en",
        )

        user_b = User(
            tenant_id=tenant_b.id,
            phone="9000000002",
            name="Bob",
            email="bob@test.com",
            role="admin",
            language="en",
        )

        session.add_all([user_a, user_b])
        await session.commit()

        await set_tenant(session, str(tenant_a.id))

        repo = Repository(
            session=session,
            tenant=TenantContext(
                tenant_id=tenant_a.id,
                user_id=user_a.id,
            ),
            model=User,
        )

        # Own tenant user should be found
        result = await repo.get(user_a.id)

        assert result is not None
        assert result.id == user_a.id

        # Other tenant user must not be visible
        result = await repo.get(user_b.id)

        assert result is None