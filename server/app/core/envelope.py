"""The B.3 response envelope.

Golden rule B.1.4: the server must never return HTML or non-envelope JSON on any
`/v1` route, **including errors**. That is enforced here rather than in each router —
every success is wrapped, and every exception path, including ones FastAPI raises
before our code runs, is converted.

The Android app parses exactly this shape and maps every code in `ApiError`, so any
drift here is a client crash.
"""

from typing import Any, Generic, TypeVar

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

T = TypeVar("T")


class PageMeta(BaseModel):
    page: int = 1
    limit: int = 20
    total: int = 0


class ApiErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = {}


class Envelope(BaseModel, Generic[T]):
    success: bool
    data: T | None = None
    error: ApiErrorBody | None = None
    meta: PageMeta | None = None


def ok(data: Any = None, meta: PageMeta | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"success": True, "data": data, "error": None}
    if meta is not None:
        payload["meta"] = meta.model_dump()
    return payload


def fail(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "success": False,
        "data": None,
        "error": {"code": code, "message": message, "details": details or {}},
    }


class ApiError(Exception):
    """Raised by services. Carries the B.3 code the app will branch on."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}


# Convenience constructors for the codes in B.3.
def not_found(resource: str, message: str | None = None) -> ApiError:
    return ApiError(
        status.HTTP_404_NOT_FOUND,
        f"{resource.upper()}_NOT_FOUND",
        message or f"No {resource} with this ID in your firm.",
    )


def forbidden_role(message: str = "Your role does not allow this.") -> ApiError:
    return ApiError(status.HTTP_403_FORBIDDEN, "FORBIDDEN_ROLE", message)


def unauthenticated(message: str = "Please sign in again.") -> ApiError:
    return ApiError(status.HTTP_401_UNAUTHORIZED, "UNAUTHENTICATED", message)


def token_expired(message: str = "Session expired.") -> ApiError:
    return ApiError(status.HTTP_401_UNAUTHORIZED, "TOKEN_EXPIRED", message)


def validation(message: str, details: dict[str, Any] | None = None) -> ApiError:
    return ApiError(status.HTTP_400_BAD_REQUEST, "VALIDATION_ERROR", message, details)


def cnr_invalid(message: str = "CNR must be 16 characters.") -> ApiError:
    return ApiError(422, "CNR_INVALID", message)


def duplicate(message: str) -> ApiError:
    return ApiError(status.HTTP_409_CONFLICT, "DUPLICATE_RESOURCE", message)


def rate_limited(message: str, retry_after_seconds: int) -> ApiError:
    return ApiError(
        429, "RATE_LIMITED", message, {"retry_after_seconds": str(retry_after_seconds)}
    )


def upstream_unavailable(message: str = "That service is not responding.") -> ApiError:
    return ApiError(503, "UPSTREAM_UNAVAILABLE", message)


def quota_exceeded(message: str, limit: int, plan: str, upgrade_to: str) -> ApiError:
    # B.14: every 402 must carry upgrade_to so the app can preselect the plan.
    return ApiError(
        402,
        "QUOTA_EXCEEDED",
        message,
        {"limit": str(limit), "plan": plan, "upgrade_to": upgrade_to},
    )


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=fail(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        # 422 -> VALIDATION_ERROR with field details, per C.3.2.
        details = {}
        for err in exc.errors():
            field = ".".join(str(p) for p in err["loc"] if p not in ("body", "query"))
            details[field or "body"] = err["msg"]
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=fail("VALIDATION_ERROR", "Please check the highlighted fields.", details),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        # Catches 404s on unknown routes and 405s — without this they return
        # FastAPI's bare {"detail": ...}, which violates B.1.4 and crashes the app.
        code = {
            401: "UNAUTHENTICATED",
            403: "FORBIDDEN_ROLE",
            404: "ROUTE_NOT_FOUND",
            405: "ROUTE_NOT_FOUND",
        }.get(exc.status_code, "INTERNAL_ERROR")
        return JSONResponse(
            status_code=exc.status_code,
            content=fail(code, str(exc.detail)),
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        # Never leak a stack trace to the client (C.3.2); Sentry gets the detail.
        return JSONResponse(
            status_code=500,
            content=fail("INTERNAL_ERROR", "Something went wrong on our side."),
        )
