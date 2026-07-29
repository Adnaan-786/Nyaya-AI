from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AuthContext, get_current_auth, get_tenant_scoped_db
from app.core.exceptions import UserNotFoundException
from app.core.responses import ApiResponse
from app.models.user import User
from app.schemas.user import MeUpdateIn, UserOut

router = APIRouter(tags=["Profile"])


async def _load_current_user(session: AsyncSession, auth: AuthContext) -> User:
    result = await session.execute(select(User).where(User.id == auth.user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise UserNotFoundException()
    return user


@router.get("/me", response_model=ApiResponse[UserOut])
async def get_me(
    auth: AuthContext = Depends(get_current_auth),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[UserOut]:
    user = await _load_current_user(session, auth)
    return ApiResponse(success=True, data=UserOut.model_validate(user))


@router.patch("/me", response_model=ApiResponse[UserOut])
async def update_me(
    payload: MeUpdateIn,
    auth: AuthContext = Depends(get_current_auth),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[UserOut]:
    user = await _load_current_user(session, auth)

    if payload.name is not None:
        user.name = payload.name
    if payload.email is not None:
        user.email = payload.email
    if payload.language is not None:
        user.language = payload.language

    await session.commit()
    await session.refresh(user)

    return ApiResponse(success=True, data=UserOut.model_validate(user))
