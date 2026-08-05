"""B.4 authentication: phone OTP + JWT, and B.14 app config."""

import logging
import random
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import envelope, security
from app.core.config import get_settings
from app.core.db import get_session
from app.integrations import email as mailer
from app.integrations import sms
from app.models import Device, OtpCode, RefreshToken, Tenant, User
from app.schemas.auth import (
    AppConfigOut,
    DeviceOut,
    DeviceRegistration,
    EmailOtpRequest,
    EmailOtpVerifyRequest,
    OnboardRequest,
    OtpRequest,
    OtpVerifyRequest,
    RefreshRequest,
    TokenPairOut,
    UserOut,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["auth"])
settings = get_settings()

OTP_TTL_MINUTES = 5
OTP_MAX_PER_HOUR = 3
OTP_MAX_ATTEMPTS = 5


async def _issue_otp(
    session: AsyncSession,
    identifier: str,
    live: bool,
    deliver: Callable[[str, str], Awaitable[None]],
) -> None:
    """The half of B.4.1 both channels share: 6 digits, 5-minute validity, 3/hour.

    `identifier` is a phone number or an email address; `deliver` is the channel that
    carries the code. Keeping this in one place is deliberate — the rate limit, the
    hashing and the rollback below are the security properties of signing in, and a
    second channel that reimplemented them would drift from this one.
    """
    now = datetime.now(UTC)
    window_start = now - timedelta(hours=1)

    recent = await session.scalars(
        select(OtpCode).where(
            OtpCode.identifier == identifier, OtpCode.created_at >= window_start
        )
    )
    if len(recent.all()) >= OTP_MAX_PER_HOUR:
        # Rate limiting an OTP endpoint is not optional: without it this is a free
        # SMS-bombing (or mail-bombing) service pointed at anyone's address.
        raise envelope.rate_limited("Too many attempts. Try again in an hour.", 3600)

    # Gated on whether this channel can actually *deliver*, not on the global flag.
    # With nothing configured the code only ever reaches a server log, so a random one
    # is no more secure than the fixed one — it just makes the app unusable for anyone
    # who turned FAKE_MODE off to enable some unrelated integration like push.
    code = f"{random.randint(0, 999999):06d}" if live else sms.FAKE_OTP
    record = OtpCode(
        identifier=identifier,
        code_hash=security.hash_otp(identifier, code),
        expires_at=now + timedelta(minutes=OTP_TTL_MINUTES),
    )
    session.add(record)
    # Committed before the send, so a code can never reach someone that this server is
    # then unable to verify.
    await session.commit()

    try:
        await deliver(identifier, code)
    except (sms.SmsDeliveryError, mailer.EmailDeliveryError, httpx.HTTPError, OSError):
        # That row already counts against OTP_MAX_PER_HOUR. Left in place, a provider
        # outage or an exhausted balance would lock someone out of their own account
        # for an hour over three codes they never received — so a failed attempt is
        # rolled back instead of held against them.
        logger.exception("could not deliver an OTP")
        await session.delete(record)
        await session.commit()
        raise envelope.upstream_unavailable(
            "We could not send your code. Please try again."
        ) from None


async def _consume_otp(session: AsyncSession, identifier: str, otp: str) -> None:
    """Verifies and burns the newest live code for `identifier`, or raises."""
    now = datetime.now(UTC)
    record = (
        await session.scalars(
            select(OtpCode)
            .where(
                OtpCode.identifier == identifier,
                OtpCode.consumed_at.is_(None),
                OtpCode.expires_at > now,
            )
            .order_by(OtpCode.created_at.desc())
            .limit(1)
        )
    ).first()

    if record is None:
        raise envelope.validation(
            "That code has expired. Please request a new one.", {"otp": "Expired"}
        )

    if record.attempts >= OTP_MAX_ATTEMPTS:
        raise envelope.rate_limited("Too many incorrect attempts.", 3600)

    if record.code_hash != security.hash_otp(identifier, otp):
        record.attempts += 1
        await session.commit()
        raise envelope.validation(
            "That code is not correct.", {"otp": "Incorrect or expired"}
        )

    record.consumed_at = now


async def _sign_in(session: AsyncSession, user: User | None, make_user: Callable[[], User]):
    """Issues the token pair, creating the account on first sight."""
    is_new_user = user is None

    if user is None:
        # A tenant is created at onboarding, not here — but a user row must exist to
        # carry the JWT. A placeholder tenant keeps tenant_id NOT NULL honest and is
        # renamed the moment /auth/onboard runs.
        tenant = Tenant(name="Pending setup")
        session.add(tenant)
        await session.flush()
        user = make_user()
        user.tenant_id = tenant.id
        session.add(user)
        await session.flush()

    pair = await _issue_tokens(session, user)
    await session.commit()
    await session.refresh(user)

    return envelope.ok(
        TokenPairOut(
            access_token=pair[0],
            refresh_token=pair[1],
            is_new_user=is_new_user,
            user=UserOut.model_validate(user),
        ).model_dump(mode="json")
    )


@router.post("/auth/otp/request")
async def request_otp(body: OtpRequest, session: AsyncSession = Depends(get_session)):
    await _issue_otp(session, body.phone, sms.is_live(), sms.send_otp)
    return envelope.ok({"ok": True})


@router.post("/auth/otp/verify")
async def verify_otp(body: OtpVerifyRequest, session: AsyncSession = Depends(get_session)):
    await _consume_otp(session, body.phone, body.otp)
    user = (await session.scalars(select(User).where(User.phone == body.phone))).first()
    return await _sign_in(
        session, user, lambda: User(name="", phone=body.phone, role="lawyer")
    )


@router.post("/auth/email/request")
async def request_email_otp(
    body: EmailOtpRequest, session: AsyncSession = Depends(get_session)
):
    """The same OTP contract as the phone channel, over SMTP.

    This exists because transactional SMS to an Indian number requires DLT
    registration — a registered business entity and weeks of template approvals —
    while email requires none of it. See app/integrations/email.py.
    """
    await _issue_otp(session, body.email, mailer.is_live(), mailer.send_otp)
    return envelope.ok({"ok": True})


@router.post("/auth/email/verify")
async def verify_email_otp(
    body: EmailOtpVerifyRequest, session: AsyncSession = Depends(get_session)
):
    await _consume_otp(session, body.email, body.otp)
    user = (await session.scalars(select(User).where(User.email == body.email))).first()
    return await _sign_in(
        session, user, lambda: User(name="", email=body.email, role="lawyer")
    )


@router.post("/auth/refresh")
async def refresh(body: RefreshRequest, session: AsyncSession = Depends(get_session)):
    """B.4.4: rotation. The presented token is revoked as the new pair is issued."""
    now = datetime.now(UTC)
    token_hash = security.hash_token(body.refresh_token)

    record = (
        await session.scalars(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
    ).first()

    if record is None or record.revoked_at is not None or record.expires_at <= now:
        # The client treats this as terminal and wipes the session, which is correct:
        # a revoked refresh token means either expiry or replay.
        raise envelope.unauthenticated("Your session has expired. Please sign in again.")

    user = await session.get(User, record.user_id)
    if user is None:
        raise envelope.unauthenticated()

    record.revoked_at = now
    pair = await _issue_tokens(session, user)
    await session.commit()

    return envelope.ok(
        TokenPairOut(
            access_token=pair[0], refresh_token=pair[1], is_new_user=False
        ).model_dump(mode="json")
    )


@router.post("/auth/onboard")
async def onboard(
    body: OnboardRequest,
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.current_principal),
):
    user = await session.get(User, principal.user_id)
    if user is None:
        raise envelope.unauthenticated()

    tenant = await session.get(Tenant, user.tenant_id)
    if tenant is not None:
        tenant.name = body.firm_name or f"{body.name}'s practice"

    user.name = body.name
    user.role = body.role_hint
    user.language = body.language
    user.bar_council_id = body.bar_council_id

    await session.commit()
    await session.refresh(user)
    return envelope.ok(UserOut.model_validate(user).model_dump(mode="json"))


@router.get("/me")
async def me(user: User = Depends(security.current_user)):
    return envelope.ok(UserOut.model_validate(user).model_dump(mode="json"))


@router.post("/devices")
async def register_device(
    body: DeviceRegistration,
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.current_principal),
):
    """B.4.6: called after every login and every FCM token refresh, so it must be
    idempotent — the same token re-registering is an update, not a duplicate."""
    existing = (
        await session.scalars(select(Device).where(Device.fcm_token == body.fcm_token))
    ).first()

    if existing is not None:
        existing.user_id = principal.user_id
        existing.tenant_id = principal.tenant_id
        existing.app_version = body.app_version
        device = existing
    else:
        device = Device(
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
            fcm_token=body.fcm_token,
            platform=body.platform,
            app_version=body.app_version,
        )
        session.add(device)

    await session.commit()
    await session.refresh(device)
    return envelope.ok(DeviceOut.model_validate(device).model_dump(mode="json"))


@router.delete("/devices/{device_id}")
async def unregister_device(
    device_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.current_principal),
):
    device = await session.get(Device, device_id)
    if device is not None and device.tenant_id == principal.tenant_id:
        await session.delete(device)
        await session.commit()
    return envelope.ok({"ok": True})


@router.get("/app/config")
async def app_config():
    """Unauthenticated by design (B.6) — the app calls this before it has a session."""
    return envelope.ok(
        AppConfigOut(
            min_supported_version=1,
            latest_version=1,
            feature_flags={
                "researcher_enabled": True,
                "draftsman_enabled": True,
                "billing_enabled": True,
            },
            status_banner=None,
            support_phone="+919000000000",
            support_email="support@nyayaai.in",
        ).model_dump(mode="json")
    )


async def _issue_tokens(session: AsyncSession, user: User) -> tuple[str, str]:
    access = security.create_access_token(user)
    raw, hashed, expiry = security.new_refresh_token()
    session.add(RefreshToken(user_id=user.id, token_hash=hashed, expires_at=expiry))
    return access, raw
