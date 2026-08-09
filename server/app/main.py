"""FastAPI entrypoint.

Every route lives under `/v1`. B.1.4 forbids non-envelope responses anywhere on that
prefix, which is why the exception handlers are installed on the app rather than being
per-router concerns.

Now that both halves of the product are ours, the OpenAPI document FastAPI generates
from these routes and their Pydantic schemas *is* the integration contract — there is
no separate hand-authored YAML to drift from.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI

from app.api import (
    ai,
    auth,
    billing,
    calendar,
    cases,
    clients,
    documents,
    notifications,
    portal,
    search,
    users,
)
from app.core import envelope
from app.core.config import get_settings
from app.core.db import ensure_schema

logging.basicConfig(
    level=logging.INFO,
    format='{"level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
)
logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Runs in every environment, unlike the `create_all()` it replaces. That gate existed
    # because `create_all()` could only ever add tables — it was never safe to point at a
    # database whose schema had moved on. Migrations are the opposite: skipping them in
    # production is what leaves the code and the schema disagreeing.
    await ensure_schema()
    yield


app = FastAPI(
    title="NyayaAI API",
    version="1.0.0",
    description=(
        "Legal practice management for Indian lawyers. All responses use the "
        "success/data/error/meta envelope; money is integer paise; calendar dates "
        "(hearing.date, next_hearing_date, due_date) are dates, not instants."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    openapi_url="/openapi.json",
)

envelope.install_exception_handlers(app)

v1 = APIRouter(prefix="/v1")
v1.include_router(auth.router)
v1.include_router(clients.router)
v1.include_router(cases.router)
v1.include_router(calendar.router)
v1.include_router(documents.router)
v1.include_router(search.router)
v1.include_router(ai.router)
v1.include_router(billing.router)
v1.include_router(portal.router)
v1.include_router(notifications.router)
v1.include_router(users.router)


@v1.get("/health", tags=["ops"])
async def health():
    return envelope.ok({"status": "ok", "environment": settings.environment})


@v1.post("/seed", tags=["ops"])
async def seed_demo():
    if settings.environment == "prod":
        return envelope.fail("forbidden", "seed is disabled in production")
    from scripts.seed_demo import seed
    await seed()
    return envelope.ok({"seeded": True})


app.include_router(v1)
