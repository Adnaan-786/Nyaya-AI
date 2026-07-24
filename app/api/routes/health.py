from fastapi import APIRouter

from app.config import get_settings
from app.core.responses import ApiResponse

router = APIRouter(tags=["Health"])

settings = get_settings()


@router.get("/health", response_model=ApiResponse[dict])
async def health_check() -> ApiResponse[dict]:
    return ApiResponse(
        success=True,
        data={
            "status": "healthy",
            "service": settings.app_name,
            "version": settings.api_version,
            "environment": settings.environment.value,
        },
    )