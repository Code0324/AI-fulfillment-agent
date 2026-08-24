"""API v1 order routes — generic in-memory fulfillment order endpoints."""

from uuid import UUID

from fastapi import APIRouter, Query, status as http_status

from app.core.errors import ValidationError
from app.schemas.order import Order, OrderCreate, OrderListResponse, OrderStatus, OrderUpdate
from app.services.order_service import order_service

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", response_model=Order, status_code=http_status.HTTP_201_CREATED)
def create_order(payload: OrderCreate) -> Order:
    """Create a new fulfillment order."""
    return order_service.create(payload)


@router.get("", response_model=OrderListResponse)
def list_orders(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page (max 100)"),
    status: OrderStatus | None = Query(None, description="Filter by order status"),
    search: str | None = Query(None, description="Search by customer, product, or order ID"),
) -> OrderListResponse:
    """List orders with optional search, status filter, and pagination."""
    return order_service.list_orders(page=page, page_size=page_size, status=status, search=search)


@router.get("/{order_id}", response_model=Order)
def get_order(order_id: UUID) -> Order:
    """Return a single order by ID (404 if missing)."""
    return order_service.get(order_id)


@router.patch("/{order_id}", response_model=Order)
def update_order(order_id: UUID, payload: OrderUpdate) -> Order:
    """Update the status of an existing order."""
    if payload.status is None:
        raise ValidationError("Field 'status' is required")
    return order_service.update_status(order_id, payload.status)


@router.post("/{order_id}/reserve", response_model=Order)
def reserve_order_inventory(order_id: UUID) -> Order:
    """Reserve inventory for an existing order."""
    return order_service.reserve_inventory(order_id)
