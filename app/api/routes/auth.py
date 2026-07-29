from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AuthContext, get_current_auth, get_tenant_scoped_db
from app.core.responses import ApiResponse
from app.db.session import get_db
from app.schemas.auth import (
    OnboardIn,
    OTPRequestIn,
    OTPVerifyIn,
    RefreshIn,
    TokenPairOut,
    TokenRefreshOut,
)
from app.schemas.user import UserOut
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/otp/request", response_model=ApiResponse[dict])
async def request_otp(
    payload: OTPRequestIn,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    await auth_service.request_otp(session, payload.phone)
    return ApiResponse(success=True, data={"sent": True})


@router.post("/otp/verify", response_model=ApiResponse[TokenPairOut])
async def verify_otp(
    payload: OTPVerifyIn,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[TokenPairOut]:
    user, is_new_user = await auth_service.verify_otp(session, payload.phone, payload.otp)
    access_token, refresh_token = await auth_service.issue_token_pair(session, user)

    return ApiResponse(
        success=True,
        data=TokenPairOut(
            access_token=access_token,
            refresh_token=refresh_token,
            is_new_user=is_new_user,
            user=UserOut.model_validate(user),
        ),
    )


@router.post("/refresh", response_model=ApiResponse[TokenRefreshOut])
async def refresh_token(
    payload: RefreshIn,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[TokenRefreshOut]:
    access_token, new_refresh_token = await auth_service.rotate_refresh_token(
        session, payload.refresh_token
    )
    return ApiResponse(
        success=True,
        data=TokenRefreshOut(access_token=access_token, refresh_token=new_refresh_token),
    )


@router.post("/onboard", response_model=ApiResponse[UserOut])
async def onboard(
    payload: OnboardIn,
    auth: AuthContext = Depends(get_current_auth),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[UserOut]:
    from app.core.exceptions import UserNotFoundException
    from app.models.user import User

    result = await session.execute(select(User).where(User.id == auth.user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise UserNotFoundException()

    user = await auth_service.onboard_user(
        session,
        user,
        name=payload.name,
        role_hint=payload.role_hint,
        firm_name=payload.firm_name,
        bar_council_id=payload.bar_council_id,
        language=payload.language,
    )

    return ApiResponse(success=True, data=UserOut.model_validate(user))
