from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import (
    AuthenticationException,
    RateLimitException,
    TokenExpiredException,
    ValidationException,
)
from app.core.security import (
    create_access_token,
    generate_otp,
    generate_refresh_token,
    hash_otp,
    hash_token,
    otp_expiry,
    refresh_token_expiry,
    utcnow,
    verify_otp_hash,
)
from app.integrations.msg91 import send_otp_sms
from app.models.otp_request import OTPRequest
from app.models.refresh_token import RefreshToken
from app.models.tenant import Tenant
from app.models.user import User

settings = get_settings()


async def request_otp(session: AsyncSession, phone: str) -> None:
    """
    Generates and "sends" an OTP for `phone`, enforcing:
      - 5-minute validity
      - max 3 sends/hour/phone
    (contract B.4.1)
    """

    now = utcnow()

    result = await session.execute(
        select(OTPRequest).where(OTPRequest.phone == phone)
    )
    otp_row = result.scalar_one_or_none()

    if otp_row is not None and otp_row.window_start is not None:
        window_age = now - otp_row.window_start
        if window_age.total_seconds() < 3600:
            if otp_row.send_count >= settings.otp_max_per_hour:
                raise RateLimitException(
                    message="Too many OTP requests. Please try again later.",
                    details={"retry_after_seconds": int(3600 - window_age.total_seconds())},
                )
        else:
            # window expired; reset it
            otp_row.window_start = now
            otp_row.send_count = 0

    code = generate_otp()

    if otp_row is None:
        otp_row = OTPRequest(
            phone=phone,
            code_hash=hash_otp(code),
            expires_at=otp_expiry(),
            attempts=0,
            send_count=1,
            window_start=now,
        )
        session.add(otp_row)
    else:
        otp_row.code_hash = hash_otp(code)
        otp_row.expires_at = otp_expiry()
        otp_row.attempts = 0
        otp_row.send_count = (otp_row.send_count or 0) + 1
        if otp_row.window_start is None:
            otp_row.window_start = now

    await session.commit()

    await send_otp_sms(phone, code)


async def _get_user_by_phone(session: AsyncSession, phone: str) -> User | None:
    result = await session.execute(select(User).where(User.phone == phone))
    return result.scalar_one_or_none()


async def verify_otp(
    session: AsyncSession, phone: str, otp: str
) -> tuple[User, bool]:
    """
    Validates the OTP for `phone`. On success, returns (user, is_new_user),
    creating a bare tenant+user shell for brand-new phones (contract B.4.2/5:
    the shell is filled in by POST /auth/onboard).
    """

    result = await session.execute(
        select(OTPRequest).where(OTPRequest.phone == phone)
    )
    otp_row = result.scalar_one_or_none()

    if otp_row is None:
        raise ValidationException("No OTP was requested for this phone number.")

    now = utcnow()

    if otp_row.expires_at < now:
        raise ValidationException("OTP has expired. Please request a new one.")

    if otp_row.attempts >= settings.otp_max_verify_attempts:
        raise RateLimitException("Too many incorrect attempts. Please request a new OTP.")

    if not verify_otp_hash(otp, otp_row.code_hash):
        otp_row.attempts += 1
        await session.commit()
        raise ValidationException("Incorrect OTP.")

    # Success: consume the OTP so it cannot be replayed.
    otp_row.attempts = 0
    otp_row.expires_at = now
    await session.commit()

    user = await _get_user_by_phone(session, phone)
    is_new_user = user is None

    if user is None:
        tenant = Tenant(name="Pending Firm")
        session.add(tenant)
        await session.flush()

        user = User(
            tenant_id=tenant.id,
            phone=phone,
            name="",
            role="pending",
            language="en",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

    return user, is_new_user


async def issue_token_pair(
    session: AsyncSession, user: User, *, family_id: UUID | None = None
) -> tuple[str, str]:
    """Issues a fresh access token + a brand-new refresh token family member."""

    access_token = create_access_token(
        user_id=user.id, tenant_id=user.tenant_id, role=user.role
    )

    refresh_token = generate_refresh_token()
    refresh_row = RefreshToken(
        user_id=user.id,
        family_id=family_id or uuid4(),
        token_hash=hash_token(refresh_token),
        expires_at=refresh_token_expiry(),
    )
    session.add(refresh_row)
    await session.commit()

    return access_token, refresh_token


async def rotate_refresh_token(
    session: AsyncSession, presented_token: str
) -> tuple[str, str]:
    """
    Rotates a refresh token: the presented token is marked revoked and a
    new token in the same family is issued. If a *revoked* token is
    presented again, the whole family is revoked (theft/replay signal),
    per contract B.4.4 "refresh rotation; old refresh token invalidated"
    and plan C.5.2 "reused refresh token revokes the whole family".
    """

    token_hash = hash_token(presented_token)

    result = await session.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    token_row = result.scalar_one_or_none()

    if token_row is None:
        raise AuthenticationException("Invalid refresh token.")

    now = utcnow()

    if token_row.revoked_at is not None:
        # Reuse of an already-rotated token: revoke the entire family.
        await session.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == token_row.family_id)
            .where(RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        await session.commit()
        raise AuthenticationException(
            "Refresh token reuse detected; all sessions for this device have been revoked."
        )

    if token_row.expires_at < now:
        raise TokenExpiredException()

    result = await session.execute(select(User).where(User.id == token_row.user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise AuthenticationException("User no longer exists.")

    token_row.revoked_at = now
    await session.commit()

    return await issue_token_pair(session, user, family_id=token_row.family_id)


async def onboard_user(
    session: AsyncSession,
    user: User,
    *,
    name: str,
    role_hint: str,
    firm_name: str | None,
    bar_council_id: str | None,
    language: str,
) -> User:
    """Fills in the profile created as a shell during OTP verify (contract B.4.5)."""

    user.name = name
    user.role = role_hint
    user.language = language
    if bar_council_id:
        user.bar_council_id = bar_council_id

    if role_hint == "firm_admin" and firm_name:
        result = await session.execute(select(Tenant).where(Tenant.id == user.tenant_id))
        tenant = result.scalar_one_or_none()
        if tenant is not None:
            tenant.name = firm_name

    await session.commit()
    await session.refresh(user)

    return user
