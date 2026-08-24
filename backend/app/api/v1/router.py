"""API v1 router — aggregates all v1 route modules."""

from fastapi import APIRouter

from app.api.v1.health import router as health_router
from app.api.v1.orders import router as orders_router
from app.api.v1.status import router as status_router
from app.api.v1.tasks import router as tasks_router

api_v1_router = APIRouter(prefix="/api/v1")

api_v1_router.include_router(health_router)
api_v1_router.include_router(status_router)
api_v1_router.include_router(tasks_router)
api_v1_router.include_router(orders_router)
