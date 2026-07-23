from typing import Any, Generic, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")

class ErrorResponse(BaseModel):
    """
    Standard error object returned by all API endpoints.
    """

    code: str = Field(..., examples=["VALIDATION_ERROR"])
    message: str = Field(..., examples=["Request validation failed"])
    details: dict[str, Any] | None = None


class ApiResponse(BaseModel, Generic[T]):
    """
    Standard API response envelope.
    """

    success: bool
    data: T | None = None
    error: ErrorResponse | None = None