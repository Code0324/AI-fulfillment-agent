"""TikTok Shop order schema.

Preserves the real business field structure (Order ID, Date, SKU, Product
Name, Variation, Qty, Recipient, Phone no, Address 1, Delivery
instructions, City, State, Zipcode, Price, Delivery Date) exactly, rather
than collapsing it into the simplified internal order shape used
elsewhere in this codebase — that shape has no room for Variation, Price,
Delivery Date, or structured address/phone, and TikTok's SKU is never
assumed to equal an Amazon SKU.

This is the real, production order representation for TikTok Shop. It is
not a mock/demo schema and is never populated with fabricated data — see
app/services/providers/tiktok/order_provider.py.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class TikTokOrder(BaseModel):
    """A single TikTok Shop order, preserving the full business field set."""

    # Traceability — kept distinct from any internal FulfillmentOrder UUID
    # at every layer, per idempotency/traceability requirements.
    tiktok_order_id: str = Field(..., description="TikTok Shop's own order ID (column A)")
    source: Literal["TIKTOK"] = Field(default="TIKTOK", description="Order source, always TIKTOK for this schema")

    # The 15-column real business structure
    order_date: datetime = Field(..., description="Order date (column B)")
    sku: str = Field(..., description="TikTok SKU (column C) — never assumed to equal an Amazon SKU")
    product_name: str = Field(..., description="Product name (column D)")
    variation: str | None = Field(None, description="Product variation, e.g. size/color (column E)")
    quantity: int = Field(..., ge=1, description="Quantity ordered (column F)")
    recipient_name: str = Field(..., description="Recipient name (column G)")
    phone_number: str = Field(..., description="Recipient phone number (column H)")
    address_line_1: str = Field(..., description="Address line 1 (column I)")
    delivery_instructions: str | None = Field(None, description="Delivery instructions (column J)")
    city: str = Field(..., description="City (column K)")
    state: str = Field(..., description="State (column L)")
    zipcode: str = Field(..., description="Zipcode (column M)")
    price: float = Field(..., ge=0, description="Order price (column N)")
    delivery_date: datetime | None = Field(None, description="Delivery date (column O)")

    # Not part of the 15-column structure but required operationally
    order_status: str = Field(..., description="TikTok's raw order status string, preserved as-is")
