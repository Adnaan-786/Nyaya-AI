"""JWT issue/verify and the request-scoped principal.

B.4.3: access tokens are 30-minute JWTs whose claims are `sub` (user_id),
`tenant_id`, `role`, `exp`. Refresh tokens are opaque, hashed at rest, 30 days, and
**rotate** on every use — the client's single-flight refresh logic depends on the old
token being invalidated the moment a new pair is issued.
"""

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Depends, Request
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session
from app.core import envelope
from app.models import User

settings = get_settings()


@dataclass(frozen=True)
class Principal:
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    role: str

    @property
    def is_client(self) -> bool:
        return self.role == "client"


def create_access_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    claims: dict[str, Any] = {
        "sub": str(user.id),
        "tenant_id": str(user.tenant_id),
        "role": user.role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.access_token_minutes)).timestamp()),
    }
    return jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def new_refresh_token() -> tuple[str, str, datetime]:
    """Returns (plaintext, hash, expiry). Only the hash is stored."""
    raw = secrets.token_urlsafe(48)
    expiry = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_days)
    return raw, hash_token(raw), expiry


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def hash_otp(phone: str, code: str) -> str:
    # Salted with the phone so identical codes for different numbers differ at rest.
    return hashlib.sha256(f"{phone}:{code}".encode()).hexdigest()


async def current_principal(request: Request) -> Principal:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise envelope.unauthenticated()

    token = header.removeprefix("Bearer ").strip()
    try:
        claims = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        # The app only refreshes on TOKEN_EXPIRED; anything else logs the user out.
        # Getting this distinction wrong causes either a refresh loop or a spurious
        # logout, so expiry is separated from every other JWT failure.
        if "expire" in str(exc).lower():
            raise envelope.token_expired() from exc
        raise envelope.unauthenticated() from exc

    return Principal(
        user_id=uuid.UUID(claims["sub"]),
        tenant_id=uuid.UUID(claims["tenant_id"]),
        role=claims.get("role", "lawyer"),
    )


async def current_user(
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> User:
    user = await session.get(User, principal.user_id)
    if user is None:
        raise envelope.unauthenticated()
    return user


def require_roles(*roles: str):
    """Server-side RBAC. B.4: the app also hides UI by role, but this is authoritative."""

    async def _guard(principal: Principal = Depends(current_principal)) -> Principal:
        if principal.role not in roles:
            raise envelope.forbidden_role()
        return principal

    return _guard


async def require_staff(principal: Principal = Depends(current_principal)) -> Principal:
    """Everything except client-mode. Clients only ever reach /portal routes."""
    if principal.is_client:
        raise envelope.forbidden_role("This area is for your legal team.")
    return principal
