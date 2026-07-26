"""B.4 authentication: phone OTP + JWT, and B.14 app config."""

import random
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import envelope, security
from app.core.config import get_settings
from app.core.db import get_session
from app.integrations import sms
from app.models import Device, OtpCode, RefreshToken, Tenant, User
from app.schemas.auth import (
    AppConfigOut,
    DeviceOut,
    DeviceRegistration,
    OnboardRequest,
    OtpRequest,
    OtpVerifyRequest,
    RefreshRequest,
    TokenPairOut,
    UserOut,
)

router = APIRouter(tags=["auth"])
settings = get_settings()

OTP_TTL_MINUTES = 5
OTP_MAX_PER_HOUR = 3
OTP_MAX_ATTEMPTS = 5


@router.post("/auth/otp/request")
async def request_otp(body: OtpRequest, session: AsyncSession = Depends(get_session)):
    """B.4.1: 6 digits, 5-minute validity, max 3/hour per phone."""
    now = datetime.now(UTC)
    window_start = now - timedelta(hours=1)

    recent = await session.scalars(
        select(OtpCode).where(OtpCode.phone == body.phone, OtpCode.created_at >= window_start)
    )
    if len(recent.all()) >= OTP_MAX_PER_HOUR:
        # Rate limiting an OTP endpoint is not optional: without it this is a free
        # SMS-bombing service pointed at any Indian mobile number.
        raise envelope.rate_limited("Too many attempts. Try again in an hour.", 3600)

    code = sms.FAKE_OTP if settings.fake_mode else f"{random.randint(0, 999999):06d}"
    session.add(
        OtpCode(
            phone=body.phone,
            code_hash=security.hash_otp(body.phone, code),
            expires_at=now + timedelta(minutes=OTP_TTL_MINUTES),
        )
    )
    await session.commit()
    await sms.send_otp(body.phone, code)
    return envelope.ok({"ok": True})


@router.post("/auth/otp/verify")
async def verify_otp(body: OtpVerifyRequest, session: AsyncSession = Depends(get_session)):
    now = datetime.now(UTC)
    record = (
        await session.scalars(
            select(OtpCode)
            .where(
                OtpCode.phone == body.phone,
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

    if record.code_hash != security.hash_otp(body.phone, body.otp):
        record.attempts += 1
        await session.commit()
        raise envelope.validation(
            "That code is not correct.", {"otp": "Incorrect or expired"}
        )

    record.consumed_at = now
    user = (await session.scalars(select(User).where(User.phone == body.phone))).first()
    is_new_user = user is None

    if user is None:
        # A tenant is created at onboarding, not here — but a user row must exist to
        # carry the JWT. A placeholder tenant keeps tenant_id NOT NULL honest and is
        # renamed the moment /auth/onboard runs.
        tenant = Tenant(name="Pending setup")
        session.add(tenant)
        await session.flush()
        user = User(tenant_id=tenant.id, name="", phone=body.phone, role="lawyer")
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
