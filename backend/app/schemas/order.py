"""Generic fulfillment order schema.

Represents a mock/demo fulfillment order for workspace UI.
Not connected to real Amazon, suppliers, or external services.
"""

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class OrderStatus(str, Enum):
    """Lifecycle states for a fulfillment order."""

    PENDING = "pending"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class Order(BaseModel):
    """A generic fulfillment order."""

    id: UUID = Field(..., description="Unique order identifier")
    customer_name: str = Field(..., min_length=1, description="Customer name")
    shipping_address: str = Field(..., min_length=1, description="Shipping address")
    product_name: str = Field(..., min_length=1, description="Product or item name")
    sku: str = Field(default="", description="Product SKU for inventory lookup")
    quantity: int = Field(..., ge=1, description="Quantity ordered")
    status: OrderStatus = Field(..., description="Current order status")
    inventory_reserved: bool = Field(default=False, description="Whether inventory has been reserved")
    created_at: datetime = Field(..., description="When the order was created")
    updated_at: datetime = Field(..., description="When the order was last updated")


class OrderCreate(BaseModel):
    """Payload for creating a new order."""

    customer_name: str = Field(..., min_length=1, description="Customer name")
    shipping_address: str = Field(..., min_length=1, description="Shipping address")
    product_name: str = Field(..., min_length=1, description="Product or item name")
    sku: str = Field(default="", description="Product SKU for inventory lookup")
    quantity: int = Field(..., ge=1, description="Quantity ordered")
    reserve_inventory: bool = Field(default=False, description="Reserve inventory on creation")
    status: OrderStatus = Field(
        default=OrderStatus.PENDING, description="Initial status"
    )


class OrderUpdate(BaseModel):
    """Payload for updating an order."""

    status: OrderStatus | None = Field(None, description="New status value")


class OrderListResponse(BaseModel):
    """Paginated response for order list endpoints."""

    items: list[Order] = Field(..., description="Page of orders")
    page: int = Field(..., ge=1, description="Current page number (1-indexed)")
    page_size: int = Field(..., ge=1, description="Items per page")
    total_items: int = Field(..., ge=0, description="Total number of orders")
    total_pages: int = Field(..., ge=0, description="Total number of pages")
