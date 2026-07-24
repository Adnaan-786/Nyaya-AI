from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.constants import ErrorCode
from app.core.envelope import error_response
from app.core.exceptions import AppException
from app.core.logging import get_logger
from app.core.responses import ApiResponse

logger = get_logger(__name__)


def json_api_response(
    response: ApiResponse,
    status_code: int,
) -> JSONResponse:
    """
    Convert an ApiResponse into a JSONResponse.
    """
    return JSONResponse(
        status_code=status_code,
        content=response.model_dump(exclude_none=True),
    )


async def app_exception_handler(
    request: Request,
    exc: AppException,
) -> JSONResponse:
    response = error_response(
        code=exc.code,
        message=exc.message,
        details=exc.details,
    )

    return json_api_response(response, exc.status_code)


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    response = error_response(
        code=ErrorCode.VALIDATION_ERROR,
        message="Request validation failed.",
        details={"errors": exc.errors()},
    )

    return json_api_response(
        response,
        status.HTTP_400_BAD_REQUEST,
    )


async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    logger.exception(
        "Unhandled exception",
        request_id = getattr(request.state, "request_id", None)
    )
    response = error_response(
        code=ErrorCode.INTERNAL_ERROR,
        message="An unexpected internal server error occurred.",
    )

    return json_api_response(
        response,
        status.HTTP_500_INTERNAL_SERVER_ERROR,
    )