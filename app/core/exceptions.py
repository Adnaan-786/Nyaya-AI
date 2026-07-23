from typing import Any
from app.core.constants import ErrorCode

class AppException(Exception):
    """
    Base exception for all application-specific errors.
    """

    def __init__(
        self,
        *,
        message: str,
        code: ErrorCode,
        status_code: int,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details

        super().__init__(message)

class ValidationException(AppException):
    def __init__(self, message: str="Validation failed", details: dict[str, Any]|None = None):
        super().__init__(
            message=message,
            code=ErrorCode.VALIDATION_ERROR,
            status_code=400,
            details=details,
        )


class AuthenticationException(AppException):
    def __init__(self, message: str="Authentication required", details: dict[str, Any]|None = None):
        super().__init__(
            message=message,
            code=ErrorCode.UNAUTHENTICATED,
            status_code=401,
            details=details,
        )


class TokenExpiredException(AppException):
    def __init__(self, details: dict[str, Any]|None = None):
        super().__init__(
            message="Authentication token has expired.",
            code=ErrorCode.TOKEN_EXPIRED,
            status_code=401,
            details=details,
        )


class QuotaExceededException(AppException):
    def __init__(self, details: dict[str, Any]|None = None):
        super().__init__(
            message="Quota has exceeded(plan limit hit).",
            code=ErrorCode.QUOTA_EXCEEDED,
            status_code=402,
            details=details,
        )


class ForbiddenRoleException(AppException):
    def __init__(self, message: str="Access denied", details: dict[str, Any]|None = None):
        super().__init__(
            message=message,
            code=ErrorCode.FORBIDDEN_ROLE,
            status_code=403,
            details=details,
        )


class CaseNotFoundException(AppException):
    def __init__(self, message: str="Case not Found", details: dict[str, Any]|None = None):
        super().__init__(
            message=message,
            code=ErrorCode.CASE_NOT_FOUND,
            status_code=404,
            details=details,
        )


class ClientNotFoundException(AppException):
    def __init__(self, message: str="Client not Found", details: dict[str, Any]|None = None):
        super().__init__(
            message=message,
            code=ErrorCode.CLIENT_NOT_FOUND,
            status_code=404,
            details=details,
        )


class DocumentNotFoundException(AppException):
    def __init__(self, message: str="Document not Found", details: dict[str, Any]|None = None):
        super().__init__(
            message=message,
            code=ErrorCode.DOCUMENT_NOT_FOUND,
            status_code=404,
            details=details,
        )


class UserNotFoundException(AppException):
    def __init__(self, message:str="User not Found", details: dict[str, Any]|None = None):
        super().__init__(
            message=message,
            code=ErrorCode.USER_NOT_FOUND,
            status_code=404,
            details=details,
        )


class DuplicateResourceException(AppException):
    def __init__(self, message: str="Resource already exists", details: dict[str, Any]|None = None):
        super().__init__(
            message=message,
            code=ErrorCode.DUPLICATE_RESOURCE,
            status_code=409,
            details=details,
        )


class CNRInvalidException(AppException):
    def __init__(self, message: str="CNR Invalid", details: dict[str, Any]|None = None):
        super().__init__(
            message=message,
            code=ErrorCode.CNR_INVALID,
            status_code=422,
            details=details
        )


class UpgradeRequiredException(AppException):
    def __init__(self, message: str="App version below minimum", details: dict[str, Any]|None = None):
        super().__init__(
            message=message,
            code=ErrorCode.UPGRADE_REQUIRED,
            status_code=426,
            details=details
        )


class RateLimitException(AppException):
    def __init__(self, message: str="Rate Limit Exceeded", details: dict[str, Any]|None = None):
        super().__init__(
            message=message,
            code=ErrorCode.RATE_LIMITED,
            status_code=429,
            details=details,
        )


class InternalErrorException(AppException):
    def __init__(self, message: str="Internal error occurred", details: dict[str, Any]|None = None):
        super().__init__(
            message=message,
            code=ErrorCode.INTERNAL_ERROR,
            status_code=500,
            details=details,
        )



class UpstreamUnavailableException(AppException):
    def __init__(self, message: str="Service temporarily unavailable", details: dict[str, Any]|None = None):
        super().__init__(
            message=message,
            code=ErrorCode.UPSTREAM_UNAVAILABLE,
            status_code=503,
            details=details,
        )

__all__ = [
    "AppException",
    "ValidationException",
    "AuthenticationException",
    "TokenExpiredException",
    "QuotaExceededException",
    "ForbiddenRoleException",
    "CaseNotFoundException",
    "ClientNotFoundException",
    "DocumentNotFoundException",
    "UserNotFoundException",
    "DuplicateResourceException",
    "CNRInvalidException",
    "UpgradeRequiredException",
    "RateLimitException",
    "InternalErrorException",
    "UpstreamUnavailableException",
]






