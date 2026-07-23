from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.exceptions import AppException
from app.core.responses import ApiResponse, ErrorResponse
from app.core.constants import ErrorCode

async def app_exception_handler(
    request: Request,
    exc: AppException,
) -> JSONResponse:
    """
    Handles all custom application exceptions.
    """

    response = ApiResponse(
        success=False,
        data=None,
        error=ErrorResponse(
            code=exc.code,
            message=exc.message,
            details=exc.details,
        ),
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=response.model_dump(exclude_none=True),
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """
    Handles FastAPI validation errors.
    """

    response = ApiResponse(
        success=False,
        data=None,
        error=ErrorResponse(
            code=ErrorCode.VALIDATION_ERROR,
            message="Request validation failed",
            details={
                "errors": exc.errors(),
            },
        ),
    )

    return JSONResponse(
        status_code=400,
        content=response.model_dump(exclude_none=True),
    )


async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """
    Handles unexpected server errors.
    """

    response = ApiResponse(
        success=False,
        data=None,
        error=ErrorResponse(
            code=ErrorCode.INTERNAL_ERROR,
            message="An unexpected error occurred.",
            details=None,
        ),
    )

    return JSONResponse(
        status_code=500,
        content=response.model_dump(exclude_none=True),
    )