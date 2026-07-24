from typing import Any, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import ErrorCode

T = TypeVar("T")

class Meta(BaseModel):
    """
    Pagination metadata.
    Included only for paginated responses.
    """
    model_config = ConfigDict(extra="forbid")
    page: int = Field(
        ...,
        ge=1,
        description="Current page number.",
    )

    limit: int = Field(
        ...,
        ge=1,
        le=100,
        description="Number of items per page.",
    )

    total: int = Field(
        ...,
        ge=0,
        description="Total number of available items.",
    )

class ErrorResponse(BaseModel):
    """
    Standard error object returned by the API.
    """
    model_config = ConfigDict(extra="forbid")
    code: ErrorCode = Field(
        ...,
        description="Application error code.",
    )
    message: str = Field(
        ...,
        description="Human-readable error message.",
    )
    details: dict[str, Any] | None = Field(
        default=None,
        description="Additional error information.",
    )


class ApiResponse[T](BaseModel):
    """
    Standard API response envelope.
    Every endpoint under /v1 must return this structure.
    """
    model_config = ConfigDict(extra="forbid")
    success: bool = Field(
        ...,
        description="Whether the request completed successfully.",
    )

    data: T | None = Field(
        default=None,
        description="Response payload.",
    )

    error: ErrorResponse | None = Field(
        default=None,
        description="Error information if the request failed.",
    )

    meta: Meta | None = Field(
        default=None,
        description="Pagination metadata. Present only for paginated responses.",
    )