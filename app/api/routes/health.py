from fastapi import APIRouter
from app.core.responses import ApiResponse

router = APIRouter(tags=["Health"])

@router.get("/health", response_model=ApiResponse[dict])
async def health_check() -> ApiResponse[dict]:
    return ApiResponse(
        success=True,
        data={
            "status": "healthy",
        },
    )