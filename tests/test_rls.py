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

        print("\n==============================")
        print("Inserted Users")
        print("==============================")

        result = await session.execute(
            text("SELECT tenant_id, phone FROM users")
        )

        for row in result:
            print(row)

        # ==================================================
        # Tenant A
        # ==================================================

        print("\n==============================")
        print("Tenant A")
        print("==============================")

        await set_tenant(session, str(tenant_a.id))

        result = await session.execute(
            text("SELECT current_user, session_user, current_setting('app.tenant_id', true)")
        )

        print("Session tenant =", result.scalar())
        print(result.first())

        result = await session.execute(
            text("SHOW row_security")
        )
        row = result.first()
        print(row)

        print("Row security =", result.scalar())

        result = await session.execute(select(User))

        users = result.scalars().all()

        print("Visible users =", len(users))

        for u in users:
            print(u.id, u.tenant_id, u.phone)

        assert len(users) == 1
        assert users[0].tenant_id == tenant_a.id

        # ==================================================
        # Tenant B
        # ==================================================

        print("\n==============================")
        print("Tenant B")
        print("==============================")

        await set_tenant(session, str(tenant_b.id))
        

        result = await session.execute(
            text("SELECT current_setting('app.tenant_id', true)")
        )

        print("Session tenant =", result.scalar())

        result = await session.execute(select(User))

        users = result.scalars().all()

        print("Visible users =", len(users))

        for u in users:
            print(u.id, u.tenant_id, u.phone)

        assert len(users) == 1
        assert users[0].tenant_id == tenant_b.id