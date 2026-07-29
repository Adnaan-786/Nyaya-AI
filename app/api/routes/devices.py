from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AuthContext, get_current_auth
from app.core.exceptions import ForbiddenRoleException, ValidationException
from app.core.responses import ApiResponse
from app.db.session import get_db
from app.models.device import Device
from app.schemas.device import DeviceIn, DeviceOut

router = APIRouter(prefix="/devices", tags=["Devices"])


@router.post("", response_model=ApiResponse[DeviceOut])
async def register_device(
    payload: DeviceIn,
    auth: AuthContext = Depends(get_current_auth),
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[DeviceOut]:
    """Upserts by fcm_token, per plan C.5.5."""

    result = await session.execute(
        select(Device).where(Device.fcm_token == payload.fcm_token)
    )
    device = result.scalar_one_or_none()

    if device is None:
        device = Device(
            user_id=auth.user_id,
            fcm_token=payload.fcm_token,
            platform=payload.platform,
            app_version=payload.app_version,
        )
        session.add(device)
    else:
        device.user_id = auth.user_id
        device.platform = payload.platform
        device.app_version = payload.app_version

    await session.commit()
    await session.refresh(device)

    return ApiResponse(success=True, data=DeviceOut.model_validate(device))


@router.delete("/{device_id}", response_model=ApiResponse[dict])
async def delete_device(
    device_id: UUID,
    auth: AuthContext = Depends(get_current_auth),
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    result = await session.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()

    if device is None:
        raise ValidationException("Device not found.")

    if device.user_id != auth.user_id:
        raise ForbiddenRoleException("You may only remove your own devices.")

    await session.delete(device)
    await session.commit()

    return ApiResponse(success=True, data={"deleted": True})
