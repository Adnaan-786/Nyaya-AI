"""Test fixtures: a live app bound to the dev database, and per-firm clients."""

import uuid
from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.db import create_all, engine
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
    await create_all()
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
    token = verified.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    await http.post(
        f"{BASE}/auth/onboard",
        headers=headers,
        json={"name": f"Adv. {firm}", "role_hint": "firm_admin", "firm_name": firm},
    )
    return headers
