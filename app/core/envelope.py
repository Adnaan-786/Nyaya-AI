from typing import Any

from app.core.constants import ErrorCode
from app.core.responses import ApiResponse, ErrorResponse, Meta

def success_response(
    data: Any = None,
    meta: Meta | None = None,
) -> ApiResponse[Any]:
    """
    Create a successful API response.
    """

    return ApiResponse(
        success=True,
        data=data,
        meta=meta,
    )


def error_response(
    *,
    code: ErrorCode,
    message: str,
    details: dict[str, Any] | None = None,
) -> ApiResponse[Any]:
    """
    Create a standardized error response.
    """

    return ApiResponse(
        success=False,
        error=ErrorResponse(
            code=code,
            message=message,
            details=details,
        ),
    )