from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from app.core.logging import configure_logging, get_logger

from app.config import get_settings
from app.core.exceptions import AppException
from app.core.handlers import (
    app_exception_handler,
    validation_exception_handler,
    unhandled_exception_handler,
)
from app.core.middleware import RequestContextMiddleware
from app.api.router import api_router

logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application startup and shutdown lifecycle.
    """
    settings = get_settings()

    # Startup
    logger.info(
        "Application starting",
        app = settings.app_name,
        environment = settings.environment.value
    )
    yield

    # Shutdown
    logger.info("Application shutting down")

def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    """
    
    configure_logging()
    
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        debug=settings.debug,
        lifespan=lifespan,
    )

    # Middleware
    app.add_middleware(RequestContextMiddleware)

    # Exception handlers
    app.add_exception_handler(
        AppException,
        app_exception_handler,
    )

    app.add_exception_handler(
        RequestValidationError,
        validation_exception_handler,
    )

    app.add_exception_handler(
        Exception,
        unhandled_exception_handler,
    )

    app.include_router(
        api_router,
        prefix = settings.api_prefix
    )

    return app