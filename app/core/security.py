"""
JWT access-token and OTP/refresh-token hashing helpers.

Per Integration Contract B.4:
  - Access token: JWT, 30-min expiry. Claims: sub (user_id), tenant_id, role, exp.
  - Refresh token: opaque random string, 30-day expiry, rotated on every use
    (see app/services/auth_service.py for rotation + reuse detection).
"""

import hashlib
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import jwt

from app.config import get_settings
from app.core.exceptions import AuthenticationException, TokenExpiredException

settings = get_settings()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Access tokens (JWT)
# ---------------------------------------------------------------------------


def create_access_token(
    *,
    user_id: UUID,
    tenant_id: UUID,
    role: str,
) -> str:
    now = utcnow()
    expires_at = now + timedelta(minutes=settings.access_token_expire_minutes)

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }

    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpiredException() from exc
    except jwt.InvalidTokenError as exc:
        raise AuthenticationException("Invalid authentication token.") from exc


# ---------------------------------------------------------------------------
# Refresh tokens (opaque, stored hashed)
# ---------------------------------------------------------------------------


def generate_refresh_token() -> str:
    """A high-entropy opaque token; only its hash is ever persisted."""
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def refresh_token_expiry() -> datetime:
    return utcnow() + timedelta(days=settings.refresh_token_expire_days)


# ---------------------------------------------------------------------------
# OTP
# ---------------------------------------------------------------------------


def generate_otp(length: int | None = None) -> str:
    length = length or settings.otp_length
    return "".join(secrets.choice(string.digits) for _ in range(length))


def hash_otp(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def verify_otp_hash(code: str, code_hash: str) -> bool:
    return secrets.compare_digest(hash_otp(code), code_hash)


def otp_expiry() -> datetime:
    return utcnow() + timedelta(minutes=settings.otp_expire_minutes)
