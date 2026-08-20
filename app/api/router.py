from fastapi import APIRouter

from app.api.routes.auth import router as auth_router
from app.api.routes.billing_lite import router as billing_lite_router
from app.api.routes.calendar import router as calendar_router
from app.api.routes.cases import router as cases_router
from app.api.routes.clients import router as clients_router
from app.api.routes.devices import router as devices_router
from app.api.routes.documents import router as documents_router
from app.api.routes.firm import router as firm_router
from app.api.routes.health import router as health_router
from app.api.routes.tasks import router as tasks_router
from app.api.routes.users import router as users_router

api_router = APIRouter()

api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(devices_router)
api_router.include_router(firm_router)
api_router.include_router(clients_router)
api_router.include_router(cases_router)
api_router.include_router(tasks_router)
api_router.include_router(billing_lite_router)
api_router.include_router(documents_router)
api_router.include_router(calendar_router)
