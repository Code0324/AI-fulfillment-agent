"""API v1 provider routes.

Provides endpoints for provider information and mock data.
All providers are LOCAL/MOCK implementations only.
"""

from fastapi import APIRouter, Query

from app.services.providers.registry import provider_registry

router = APIRouter(prefix="/providers", tags=["providers"])


@router.get("")
def list_providers():
    """List all registered providers and their capabilities."""
    return {
        "providers": provider_registry.list_all(),
        "mock_only": True,
        "environment": "sandbox",
        "notice": "All providers are LOCAL/MOCK implementations only",
    }


@router.get("/orders")
def list_mock_orders(
    limit: int = Query(100, ge=1, le=1000, description="Max orders to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
):
    """List mock orders from the order provider."""
    provider = provider_registry.get_order_provider()
    orders = provider.list_orders(limit=limit, offset=offset)
    return {
        "orders": orders,
        "total": provider.get_order_count(),
        "provider": provider.provider_name,
        "environment": provider.environment.value,
    }


@router.get("/orders/{order_id}")
def get_mock_order(order_id: str):
    """Get a mock order by ID."""
    provider = provider_registry.get_order_provider()
    order = provider.get_order(order_id)
    if order is None:
        return {"error": "Order not found", "order_id": order_id}
    return {"order": order, "provider": provider.provider_name}


@router.get("/tracking")
def list_mock_tracking(
    limit: int = Query(100, ge=1, le=1000, description="Max records to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
):
    """List mock tracking records from the tracking provider."""
    provider = provider_registry.get_tracking_provider()
    records = provider.list_tracking(limit=limit, offset=offset)
    return {
        "tracking": records,
        "total": len(records),
        "provider": provider.provider_name,
        "environment": provider.environment.value,
    }


@router.get("/tracking/{tracking_id}")
def get_mock_tracking(tracking_id: str):
    """Get mock tracking information by ID."""
    provider = provider_registry.get_tracking_provider()
    tracking = provider.get_tracking(tracking_id)
    if tracking is None:
        return {"error": "Tracking not found", "tracking_id": tracking_id}
    return {"tracking": tracking, "provider": provider.provider_name}
