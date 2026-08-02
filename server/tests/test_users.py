"""Team management: roster visibility, role changes, and removal (B.4).

Onboarding always mints a fresh tenant, so a second team member in the *same* tenant
is seeded directly through the DB session (see `_second_user_in_same_tenant`) — this
mirrors what a real second signup into an already-provisioned firm looks like, since
there is deliberately no create-member endpoint (people join by signing in with OTP).
"""

import uuid

import pytest
from httpx import AsyncClient

from app.core import security
from app.core.db import SessionFactory
from app.models import User
from tests.conftest import BASE, sign_in

pytestmark = pytest.mark.asyncio


async def _me(http: AsyncClient, headers: dict) -> dict:
    return (await http.get(f"{BASE}/me", headers=headers)).json()["data"]


async def _second_user_in_same_tenant(tenant_id: str, role: str = "lawyer") -> dict:
    async with SessionFactory() as session:
        user = User(
            tenant_id=uuid.UUID(tenant_id),
            name="Colleague",
            phone=f"9{uuid.uuid4().int % 10**9:09d}",
            role=role,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        token = security.create_access_token(user)
        return {"headers": {"Authorization": f"Bearer {token}"}, "id": str(user.id)}


async def test_list_users_excludes_clients(client: AsyncClient) -> None:
    """B.4: client-role logins are portal accounts, not team members, and must never
    appear in the roster — a staff member's own view of "who is on my team"."""
    headers = await sign_in(client, "Roster Firm")
    me = await _me(client, headers)
    colleague = await _second_user_in_same_tenant(me["tenant_id"])

    async with SessionFactory() as session:
        session.add(
            User(
                tenant_id=uuid.UUID(me["tenant_id"]),
                name="Portal client",
                phone=f"9{uuid.uuid4().int % 10**9:09d}",
                role="client",
            )
        )
        await session.commit()

    # Any staff member — not just the admin — can see the roster, matching
    # clients.py's precedent of require_staff (not admin-only) for list endpoints.
    listed = (await client.get(f"{BASE}/users", headers=colleague["headers"])).json()["data"]
    names = {u["name"] for u in listed}
    assert "Portal client" not in names
    assert "Colleague" in names


async def test_patch_users_is_rejected_for_non_admins(client: AsyncClient) -> None:
    headers = await sign_in(client, "Guarded Firm")
    me = await _me(client, headers)
    colleague = await _second_user_in_same_tenant(me["tenant_id"], role="lawyer")

    response = await client.patch(
        f"{BASE}/users/{me['id']}",
        headers=colleague["headers"],
        json={"role": "intern"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN_ROLE"


async def test_admin_cannot_change_their_own_role(client: AsyncClient) -> None:
    headers = await sign_in(client, "SelfGuard Firm")
    me = await _me(client, headers)

    response = await client.patch(
        f"{BASE}/users/{me['id']}", headers=headers, json={"role": "lawyer"}
    )
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_admin_can_change_a_colleagues_role(client: AsyncClient) -> None:
    headers = await sign_in(client, "Promote Firm")
    me = await _me(client, headers)
    colleague = await _second_user_in_same_tenant(me["tenant_id"], role="intern")

    response = await client.patch(
        f"{BASE}/users/{colleague['id']}", headers=headers, json={"role": "lawyer"}
    )
    assert response.json()["data"]["role"] == "lawyer"


async def test_removing_a_member_soft_deletes_them_off_the_roster(
    client: AsyncClient,
) -> None:
    headers = await sign_in(client, "Offboard Firm")
    me = await _me(client, headers)
    colleague = await _second_user_in_same_tenant(me["tenant_id"])

    response = await client.delete(f"{BASE}/users/{colleague['id']}", headers=headers)
    assert response.json()["data"]["ok"] is True

    listed = (await client.get(f"{BASE}/users", headers=headers)).json()["data"]
    assert all(u["id"] != colleague["id"] for u in listed)


async def test_admin_cannot_remove_themselves(client: AsyncClient) -> None:
    headers = await sign_in(client, "NoSelfRemove Firm")
    me = await _me(client, headers)

    response = await client.delete(f"{BASE}/users/{me['id']}", headers=headers)
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
