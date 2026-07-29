import asyncio
import sys
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import AsyncSessionLocal

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

@pytest.fixture(scope="session")
def client():
    return TestClient(app)

@pytest_asyncio.fixture
async def db_session():
    async with AsyncSessionLocal() as session:
        trans = await session.begin()
        try:
            yield session
        finally:
            await trans.rollback()
