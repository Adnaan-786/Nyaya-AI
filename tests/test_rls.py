import random
import uuid

import pytest
from sqlalchemy import select, text

from app.db.rls import set_tenant
from app.db.session import AsyncSessionLocal
from app.models.tenant import Tenant
from app.models.user import User


@pytest.mark.asyncio
async def test_rls_isolation():
    async with AsyncSessionLocal() as session:
        # -----------------------------
        # Create tenants
        # -----------------------------
        tenant_a = Tenant(id=uuid.uuid4(), name="Firm A", plan="free")
        tenant_b = Tenant(id=uuid.uuid4(), name="Firm B", plan="free")

        session.add_all([tenant_a, tenant_b])
        await session.flush()

        # -----------------------------
        # Create users
        # -----------------------------
        user_a = User(
            tenant_id=tenant_a.id,
            phone=str(random.randint(6000000000, 9999999999)),
            name="Alice",
            email="alice@test.com",
            role="admin",
            language="en",
        )
        user_b = User(
            tenant_id=tenant_b.id,
            phone=str(random.randint(6000000000, 9999999999)),
            name="Bob",
            email="bob@test.com",
            role="admin",
            language="en",
        )

        session.add_all([user_a, user_b])
        await session.commit()

        # ==================================================
        # Tenant A
        # ==================================================
        await set_tenant(session, str(tenant_a.id))

        result = await session.execute(
            text("SELECT current_user, session_user, current_setting('app.tenant_id', true)")
        )
        row = result.first()
        print("Session tenant =", row[2])
        print(row)

        result = await session.execute(text("SHOW row_security"))
        row = result.first()
        print("Row security =", row[0])

        result = await session.execute(select(User))
        users = result.scalars().all()

        assert len(users) == 1
        assert users[0].tenant_id == tenant_a.id

        # ==================================================
        # Tenant B
        # ==================================================
        await set_tenant(session, str(tenant_b.id))

        result = await session.execute(
            text("SELECT current_setting('app.tenant_id', true)")
        )
        row = result.first()
        print("Session tenant =", row[0])

        result = await session.execute(select(User))
        users = result.scalars().all()

        assert len(users) == 1
        assert users[0].tenant_id == tenant_b.id
