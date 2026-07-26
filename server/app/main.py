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

from app.api import ai, auth, billing, calendar, cases, clients, documents, portal, search
from app.core import envelope
from app.core.config import get_settings
from app.core.db import create_all

logging.basicConfig(
    level=logging.INFO,
    format='{"level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
)
logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.environment == "local":
        # Local convenience only. Staging and production go through Alembic so schema
        # changes are reviewable and reversible.
        await create_all()
        logger.info("local schema ensured")
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


@v1.get("/health", tags=["ops"])
async def health():
    return envelope.ok({"status": "ok", "environment": settings.environment})


app.include_router(v1)
