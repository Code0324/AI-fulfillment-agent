"""Generic fulfillment order schema.

Represents a mock/demo fulfillment order for workspace UI.
Not connected to real Amazon, suppliers, or external services.
"""

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field, computed_field


class OrderStatus(str, Enum):
    """Lifecycle states for a fulfillment order."""

    PENDING = "pending"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class SheetSyncStatus(str, Enum):
    """Google Sheet synchronization status for an order.

    Derived from sheet_synced_at/sheet_sync_error rather than stored as its
    own column — the two existing fields are the single source of truth,
    this just names the three states plainly per the business requirement:
    PENDING (not yet attempted or not applicable), SYNCED (last attempt
    succeeded), FAILED (last attempt failed — safe to retry; the order
    itself was never lost).
    """

    PENDING = "pending"
    SYNCED = "synced"
    FAILED = "failed"


class Order(BaseModel):
    """A generic fulfillment order."""

    id: UUID = Field(..., description="Unique order identifier")
    organization_id: UUID = Field(..., description="Owning organization")
    customer_name: str = Field(..., min_length=1, description="Customer name")
    shipping_address: str = Field(..., min_length=1, description="Shipping address")
    product_name: str = Field(..., min_length=1, description="Product or item name")
    sku: str = Field(default="", description="Product SKU for inventory lookup")
    variation: str | None = Field(
        None, description="Product variation (e.g. size/color) — set for TikTok-sourced orders"
    )
    quantity: int = Field(..., ge=1, description="Quantity ordered")
    status: OrderStatus = Field(..., description="Current order status")
    source: str = Field(
        default="MANUAL", description="Order source: MANUAL, AMAZON, MOCK_AMAZON, or TIKTOK"
    )
    inventory_reserved: bool = Field(default=False, description="Whether inventory has been reserved")
    tiktok_order_id: str | None = Field(None, description="TikTok Shop's own order ID, set for TIKTOK-sourced orders")
    channel_metadata: dict | None = Field(
        None,
        description="Channel-specific fields (e.g. TikTok phone/address/price/delivery_date) — see app.schemas.tiktok.TikTokOrder",
    )
    sheet_synced_at: datetime | None = Field(None, description="When this order was last successfully synced to Google Sheets")
    sheet_sync_error: str | None = Field(None, description="Last Google Sheets sync error, if any — never fabricated")
    created_at: datetime = Field(..., description="When the order was created")
    updated_at: datetime = Field(..., description="When the order was last updated")

    @computed_field(description="Google Sheet sync status: pending, synced, or failed")  # type: ignore[misc]
    @property
    def sheet_sync_status(self) -> SheetSyncStatus:
        if self.sheet_sync_error:
            return SheetSyncStatus.FAILED
        if self.sheet_synced_at:
            return SheetSyncStatus.SYNCED
        return SheetSyncStatus.PENDING


class OrderCreate(BaseModel):
    """Payload for creating a new order."""

    customer_name: str = Field(..., min_length=1, description="Customer name")
    shipping_address: str = Field(..., min_length=1, description="Shipping address")
    product_name: str = Field(..., min_length=1, description="Product or item name")
    sku: str = Field(default="", description="Product SKU for inventory lookup")
    variation: str | None = Field(
        None, description="Product variation (e.g. size/color) — set for TikTok-sourced orders"
    )
    quantity: int = Field(..., ge=1, description="Quantity ordered")
    reserve_inventory: bool = Field(default=False, description="Reserve inventory on creation")
    status: OrderStatus = Field(
        default=OrderStatus.PENDING, description="Initial status"
    )
    source: str = Field(
        default="MANUAL", description="Order source: MANUAL, AMAZON, MOCK_AMAZON, or TIKTOK"
    )
    tiktok_order_id: str | None = Field(None, description="TikTok Shop's own order ID, set for TIKTOK-sourced orders")
    channel_metadata: dict | None = Field(
        None, description="Channel-specific fields — see app.schemas.tiktok.TikTokOrder"
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
