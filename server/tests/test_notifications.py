"""Notification inbox: per-user scoping and mark-read behaviour (B.8).

A notification is addressed to one user, not the whole firm, so the isolation that
matters here is per-*user* within a single tenant — a different axis from the
cross-tenant checks in test_tenant_isolation.py, but just as load-bearing: without it
one lawyer could read (and mark read) a colleague's push notifications.
"""

import uuid

import pytest
from httpx import AsyncClient

from app.core import security
from app.core.db import SessionFactory
from app.models import Notification, User
from tests.conftest import BASE, sign_in

pytestmark = pytest.mark.asyncio


async def _me(http: AsyncClient, headers: dict) -> dict:
    return (await http.get(f"{BASE}/me", headers=headers)).json()["data"]


async def _second_user_in_same_tenant(tenant_id: str) -> dict:
    """Onboarding always mints a fresh tenant (see app/api/auth.py), so there is no
    API path to a second staff login inside an *existing* tenant. Seeding the row
    directly is what a real second team member landing in an already-provisioned
    firm looks like at the DB level.
    """
    async with SessionFactory() as session:
        user = User(
            tenant_id=uuid.UUID(tenant_id),
            name="Colleague",
            phone=f"9{uuid.uuid4().int % 10**9:09d}",
            role="lawyer",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        token = security.create_access_token(user)
        return {"headers": {"Authorization": f"Bearer {token}"}, "id": str(user.id)}


async def _seed_notification(tenant_id: str, user_id: str, title: str) -> None:
    async with SessionFactory() as session:
        session.add(
            Notification(
                tenant_id=uuid.UUID(tenant_id),
                user_id=uuid.UUID(user_id),
                type="hearing_reminder",
                title=title,
                body="body",
            )
        )
        await session.commit()


async def test_notifications_are_scoped_to_the_signed_in_user(client: AsyncClient) -> None:
    headers = await sign_in(client, "Inbox Firm")
    me = await _me(client, headers)
    colleague = await _second_user_in_same_tenant(me["tenant_id"])

    await _seed_notification(me["tenant_id"], me["id"], "For the admin")
    await _seed_notification(me["tenant_id"], colleague["id"], "For the colleague")

    mine = (await client.get(f"{BASE}/notifications", headers=headers)).json()["data"]
    theirs = (
        await client.get(f"{BASE}/notifications", headers=colleague["headers"])
    ).json()["data"]

    assert [n["title"] for n in mine] == ["For the admin"]
    assert [n["title"] for n in theirs] == ["For the colleague"]


async def test_mark_read_is_idempotent(client: AsyncClient) -> None:
    headers = await sign_in(client, "ReadTwice Firm")
    me = await _me(client, headers)
    await _seed_notification(me["tenant_id"], me["id"], "Ping")

    listed = (await client.get(f"{BASE}/notifications", headers=headers)).json()["data"]
    notification_id = listed[0]["id"]

    first = await client.patch(
        f"{BASE}/notifications/{notification_id}/read", headers=headers
    )
    assert first.json()["data"]["read_at"] is not None
    first_read_at = first.json()["data"]["read_at"]

    second = await client.patch(
        f"{BASE}/notifications/{notification_id}/read", headers=headers
    )
    assert second.json()["success"] is True
    assert second.json()["data"]["read_at"] == first_read_at


async def test_cannot_mark_another_users_notification_read(client: AsyncClient) -> None:
    headers = await sign_in(client, "Cross User Firm")
    me = await _me(client, headers)
    colleague = await _second_user_in_same_tenant(me["tenant_id"])
    await _seed_notification(me["tenant_id"], colleague["id"], "Not yours")

    listed = (
        await client.get(f"{BASE}/notifications", headers=colleague["headers"])
    ).json()["data"]
    notification_id = listed[0]["id"]

    response = await client.patch(
        f"{BASE}/notifications/{notification_id}/read", headers=headers
    )
    assert response.json()["error"]["code"] == "NOTIFICATION_NOT_FOUND"


async def test_read_all_marks_only_the_callers_notifications(client: AsyncClient) -> None:
    headers = await sign_in(client, "ReadAll Firm")
    me = await _me(client, headers)
    colleague = await _second_user_in_same_tenant(me["tenant_id"])

    await _seed_notification(me["tenant_id"], me["id"], "One")
    await _seed_notification(me["tenant_id"], me["id"], "Two")
    await _seed_notification(me["tenant_id"], colleague["id"], "Colleague's")

    response = await client.post(f"{BASE}/notifications/read-all", headers=headers)
    assert response.json()["data"]["updated"] == 2

    theirs = (
        await client.get(
            f"{BASE}/notifications?unread_only=true", headers=colleague["headers"]
        )
    ).json()["data"]
    assert len(theirs) == 1
