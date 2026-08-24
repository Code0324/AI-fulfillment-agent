"""Generic inventory schema.

Represents a mock/demo inventory item for workspace UI.
Not connected to real Amazon, suppliers, or external services.
"""

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class InventoryStatus(str, Enum):
    """Lifecycle states for an inventory item."""

    IN_STOCK = "in_stock"
    LOW_STOCK = "low_stock"
    OUT_OF_STOCK = "out_of_stock"


class InventoryItem(BaseModel):
    """A generic inventory item."""

    id: UUID = Field(..., description="Unique inventory identifier")
    sku: str = Field(..., min_length=1, description="Product SKU or identifier")
    product_name: str = Field(..., min_length=1, description="Product name")
    current_stock: int = Field(..., ge=0, description="Current stock quantity")
    reserved_quantity: int = Field(..., ge=0, description="Reserved quantity")
    available_quantity: int = Field(..., ge=0, description="Available quantity (computed)")
    low_stock_threshold: int = Field(
        default=10, ge=0, description="Low stock threshold"
    )
    status: InventoryStatus = Field(..., description="Current inventory status")
    created_at: datetime = Field(..., description="When the item was created")
    updated_at: datetime = Field(..., description="When the item was last updated")


class InventoryCreate(BaseModel):
    """Payload for creating a new inventory item."""

    sku: str = Field(..., min_length=1, description="Product SKU or identifier")
    product_name: str = Field(..., min_length=1, description="Product name")
    current_stock: int = Field(..., ge=0, description="Current stock quantity")
    reserved_quantity: int = Field(default=0, ge=0, description="Reserved quantity")
    low_stock_threshold: int = Field(
        default=10, ge=0, description="Low stock threshold"
    )


class InventoryUpdate(BaseModel):
    """Payload for updating an inventory item."""

    current_stock: int | None = Field(None, ge=0, description="New stock quantity")
    reserved_quantity: int | None = Field(
        None, ge=0, description="New reserved quantity"
    )
    low_stock_threshold: int | None = Field(
        None, ge=0, description="New low stock threshold"
    )


class InventoryListResponse(BaseModel):
    """Paginated response for inventory list endpoints."""

    items: list[InventoryItem] = Field(..., description="Page of inventory items")
    page: int = Field(..., ge=1, description="Current page number (1-indexed)")
    page_size: int = Field(..., ge=1, description="Items per page")
    total_items: int = Field(..., ge=0, description="Total number of items")
    total_pages: int = Field(..., ge=0, description="Total number of pages")
