import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AuthContext, get_current_auth, get_tenant_scoped_db
from app.core.security import utcnow
from app.core.responses import ApiResponse
from app.schemas.case import HearingOut
from app.services import calendar_service

router = APIRouter(prefix="/calendar", tags=["Calendar"])


@router.get("", response_model=ApiResponse[dict[str, list[HearingOut]]])
async def get_calendar(
    date_from: datetime.date = Query(..., alias="from"),
    date_to: datetime.date = Query(..., alias="to"),
    auth: AuthContext = Depends(get_current_auth),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[dict[str, list[HearingOut]]]:
    grouped = await calendar_service.get_hearings_in_range(
        session, auth, date_from=date_from, date_to=date_to
    )
    return ApiResponse(
        success=True,
        data={
            date_str: [HearingOut.model_validate(h) for h in hearings]
            for date_str, hearings in grouped.items()
        },
    )


@router.get("/today", response_model=ApiResponse[list[HearingOut]])
async def get_calendar_today(
    auth: AuthContext = Depends(get_current_auth),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[list[HearingOut]]:
    today = utcnow().date()
    grouped = await calendar_service.get_hearings_in_range(
        session, auth, date_from=today, date_to=today
    )
    hearings = grouped.get(today.isoformat(), [])
    return ApiResponse(success=True, data=[HearingOut.model_validate(h) for h in hearings])
