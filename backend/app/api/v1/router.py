"""API v1 router — aggregates all v1 route modules."""

from fastapi import APIRouter

from app.api.v1.address import router as address_router
from app.api.v1.amazon import router as amazon_router
from app.api.v1.automation import router as automation_router
from app.api.v1.fulfillment import router as fulfillment_router
from app.api.v1.health import router as health_router
from app.api.v1.inventory import router as inventory_router
from app.api.v1.mock_amazon import router as mock_amazon_router
from app.api.v1.orders import router as orders_router
from app.api.v1.providers import router as providers_router
from app.api.v1.status import router as status_router
from app.api.v1.tasks import router as tasks_router

api_v1_router = APIRouter(prefix="/api/v1")

api_v1_router.include_router(health_router)
api_v1_router.include_router(status_router)
api_v1_router.include_router(tasks_router)
api_v1_router.include_router(orders_router)
api_v1_router.include_router(inventory_router)
api_v1_router.include_router(automation_router)
api_v1_router.include_router(address_router)
api_v1_router.include_router(fulfillment_router)
api_v1_router.include_router(providers_router)
api_v1_router.include_router(mock_amazon_router)
api_v1_router.include_router(amazon_router)
