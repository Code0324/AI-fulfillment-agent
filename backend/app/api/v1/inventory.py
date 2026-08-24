"""API v1 inventory routes — generic in-memory inventory endpoints."""

from uuid import UUID

from fastapi import APIRouter, Query, status as http_status

from app.core.errors import ValidationError
from app.schemas.inventory import (
    InventoryCreate,
    InventoryItem,
    InventoryListResponse,
    InventoryStatus,
    InventoryUpdate,
)
from app.services.inventory_service import inventory_service

router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.post("", response_model=InventoryItem, status_code=http_status.HTTP_201_CREATED)
def create_inventory_item(payload: InventoryCreate) -> InventoryItem:
    """Create a new inventory item."""
    return inventory_service.create(payload)


@router.get("", response_model=InventoryListResponse)
def list_inventory_items(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page (max 100)"),
    status: InventoryStatus | None = Query(None, description="Filter by inventory status"),
    search: str | None = Query(None, description="Search by SKU, product name, or item ID"),
) -> InventoryListResponse:
    """List inventory items with optional search, status filter, and pagination."""
    return inventory_service.list_items(page=page, page_size=page_size, status=status, search=search)


@router.get("/{item_id}", response_model=InventoryItem)
def get_inventory_item(item_id: UUID) -> InventoryItem:
    """Return a single inventory item by ID (404 if missing)."""
    return inventory_service.get(item_id)


@router.patch("/{item_id}", response_model=InventoryItem)
def update_inventory_item(item_id: UUID, payload: InventoryUpdate) -> InventoryItem:
    """Update an inventory item."""
    # Validate at least one field is provided
    if (
        payload.current_stock is None
        and payload.reserved_quantity is None
        and payload.low_stock_threshold is None
    ):
        raise ValidationError("At least one field must be provided")
    return inventory_service.update(item_id, payload)
