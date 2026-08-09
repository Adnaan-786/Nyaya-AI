"""Test fixtures: a live app bound to the dev database, and per-firm clients."""

import uuid
from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.db import engine, ensure_schema
from app.main import app

BASE = "http://test/v1"


@pytest_asyncio.fixture(autouse=True)
async def _isolated_engine() -> AsyncGenerator[None, None]:
    """Dispose the connection pool around every test.

    The engine is a module-level singleton, so its pooled connections bind to
    whichever event loop created them. pytest-asyncio runs each test on a fresh loop,
    and reusing a connection across loops raises "attached to a different loop".
    Disposing is cheaper and less fragile than reshaping the app to build an engine
    per test.
    """
    await engine.dispose()
    await ensure_schema()
    yield
    await engine.dispose()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as http:
        yield http


async def sign_in(http: AsyncClient, firm: str) -> dict[str, str]:
    """Creates a fresh firm with its own lawyer and returns an auth header.

    Each call uses a unique phone number so tests never collide on the global
    `users.phone` uniqueness constraint or on the per-phone OTP rate limit.
    """
    phone = f"9{uuid.uuid4().int % 10**9:09d}"

    await http.post(f"{BASE}/auth/otp/request", json={"phone": phone})
    verified = await http.post(
        f"{BASE}/auth/otp/verify", json={"phone": phone, "otp": "123456"}
    )
    data = verified.json()["data"]
    token = data["access_token"]
    refresh_token = data["refresh_token"]
    headers = {"Authorization": f"Bearer {token}"}

    await http.post(
        f"{BASE}/auth/onboard",
        headers=headers,
        json={"name": f"Adv. {firm}", "role_hint": "firm_admin", "firm_name": firm},
    )

    # The access token minted at OTP-verify time carries the pre-onboarding role
    # (new users default to "lawyer"); onboarding changes the DB row but does not
    # reissue the token. Refresh once so callers that check role (e.g. require_roles)
    # see the real post-onboarding role, the same way the app would after its own
    # onboarding screen calls refresh.
    refreshed = await http.post(
        f"{BASE}/auth/refresh", json={"refresh_token": refresh_token}
    )
    new_token = refreshed.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {new_token}"}
