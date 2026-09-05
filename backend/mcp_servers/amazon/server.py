"""Amazon MCP server.

Exposes the EXISTING Amazon integration (app.services.providers.amazon) and
the existing fulfillment safety-gate (app.services.fulfillment.workflow) as
MCP tools. Nothing here reimplements SP-API or browser automation — every
tool is a thin pass-through to code that already exists in this repo.

Tool coverage vs. what this codebase actually integrates with Amazon:

- get_order_status / get_tracking wrap AmazonOrderProvider, the existing
  read-only SP-API Orders API (sandbox) integration.
- get_product / check_price / the Amazon-side half of check_inventory go
  through app.services.providers.pricing_base.PricingProviderBase (the
  active implementation is selected once, process-wide, via
  app.services.providers.registry — see PRICING_PROVIDER in
  app/core/config.py). SP-API itself still has no Catalog/Pricing API
  integration (see app/services/providers/amazon/sp_api_client.py, Orders
  API only) — these three tools never call SP-API for this; they call the
  pricing provider instead. If that provider isn't configured (default
  "mock" always is; "pa_api"/"scrape" may not be), these report that
  honestly rather than fabricating data.
- check_inventory ALSO resolves the ASIN to an internal SKU via a
  *confirmed* (status=matched) app.services.sku_mapping row and reads the
  in-memory app.services.inventory_service the fulfillment workflow itself
  checks — this internal-warehouse view and the pricing provider's
  Amazon-side availability view answer different questions (our stock vs.
  Amazon's listing availability) and are both returned, clearly labeled.
- create_order does NOT execute a supplier submission directly. It creates
  an order via app.services.order_service and starts
  app.services.fulfillment.workflow.fulfillment_engine — the same
  approval-gated pipeline every order in this system goes through
  (inventory check, address validation, human approval before any
  submission). It returns status="pending_approval" whenever the workflow
  reaches WAITING_APPROVAL; nothing is ever auto-approved from here. Its
  optional `asin` argument is written straight through to Order.asin (a
  first-class column — see app/models.py) and is what the price
  safety-gate checks first, ahead of TikTok's SKU-mapping fallback.
"""

import logging
from uuid import UUID

from mcp.server.mcpserver import MCPServer
from sqlalchemy import select

from app.models import SkuMapping
from app.schemas.fulfillment import FulfillmentStatus
from app.schemas.order import OrderCreate
from app.services.fulfillment.workflow import fulfillment_engine
from app.services.inventory_service import inventory_service
from app.services.order_service import bridge_session, order_service, run_on_bridge_loop
from app.services.providers.amazon.order_provider import AmazonOrderProvider
from app.services.providers.pricing_base import PricingProviderError
from app.services.providers.registry import provider_registry

logger = logging.getLogger(__name__)

mcp = MCPServer("amazon")

# One provider instance, shared across tool calls in this process — mirrors
# how the rest of the app uses a single AmazonOrderProvider per process
# (see app.services.providers.registry).
_provider = AmazonOrderProvider()


def _resolve_sku_for_asin(asin: str) -> str | None:
    """Look up a confirmed (status=matched) Amazon SKU for this ASIN via the
    existing sku_mappings table. Never guesses from a fuzzy/unmatched row —
    same "only matched is trustworthy" rule as
    app.services.sku_mapping.engine.
    """

    async def _run() -> str | None:
        async with bridge_session() as db:
            stmt = select(SkuMapping).where(
                SkuMapping.asin == asin, SkuMapping.status == "matched"
            )
            result = await db.execute(stmt)
            row = result.scalars().first()
            return row.amazon_sku if row else None

    return run_on_bridge_loop(_run())


def _pricing_error_result(asin: str, e: PricingProviderError) -> dict:
    provider = provider_registry.get_pricing_provider()
    return {
        "asin": asin,
        "configured": provider.is_configured,
        "provider": provider.provider_name,
        "error": e.message,
    }


@mcp.tool()
def get_product(asin: str) -> dict:
    """Look up Amazon product details (currently: title) for an ASIN via the
    active pricing provider (see app.services.providers.registry —
    PRICING_PROVIDER selects pa_api/mock/scrape). SP-API itself has no
    Catalog Items API in this codebase; this does not call SP-API.
    """
    provider = provider_registry.get_pricing_provider()
    try:
        result = provider.get_product_details(asin)
    except PricingProviderError as e:
        return _pricing_error_result(asin, e)
    return {**result, "configured": True}


@mcp.tool()
def check_price(asin: str) -> dict:
    """Look up the current Amazon price for an ASIN via the active pricing
    provider (see app.services.providers.registry — PRICING_PROVIDER
    selects pa_api/mock/scrape). SP-API itself has no Pricing API in this
    codebase; this does not call SP-API.
    """
    provider = provider_registry.get_pricing_provider()
    try:
        result = provider.get_price(asin)
    except PricingProviderError as e:
        return _pricing_error_result(asin, e)
    return {**result, "configured": True}


@mcp.tool()
def check_inventory(asin: str) -> dict:
    """Check inventory/availability for an ASIN from two distinct sources:

    - "internal": our own warehouse-style stock, via a confirmed SKU
      mapping (app.services.sku_mapping) into app.services.inventory_service
      — the same store the fulfillment workflow itself checks.
    - "amazon": Amazon's own listing availability, via the active pricing
      provider (see app.services.providers.registry). These answer
      different questions and are never merged into one number.
    """
    amazon_sku = _resolve_sku_for_asin(asin)
    if amazon_sku is None:
        internal = {
            "found": False,
            "reason": "No confirmed SKU mapping (app.services.sku_mapping) for this ASIN.",
        }
    else:
        item = inventory_service.find_by_sku(amazon_sku)
        if item is None:
            internal = {
                "sku": amazon_sku,
                "found": False,
                "reason": "No inventory record for the resolved SKU.",
            }
        else:
            internal = {
                "sku": amazon_sku,
                "found": True,
                "available_quantity": item.available_quantity,
                "current_stock": item.current_stock,
                "reserved_quantity": item.reserved_quantity,
                "status": item.status.value,
            }

    provider = provider_registry.get_pricing_provider()
    try:
        amazon = {**provider.get_inventory_status(asin), "configured": True}
    except PricingProviderError as e:
        amazon = _pricing_error_result(asin, e)

    return {"asin": asin, "internal": internal, "amazon": amazon}


@mcp.tool()
def get_order_status(order_id: str) -> dict:
    """Get an Amazon order's status via the existing read-only SP-API sandbox provider."""
    if not _provider.is_configured:
        return {
            "order_id": order_id,
            "configured": False,
            "reason": "Amazon SP-API credentials not configured (see AmazonOrderProvider.is_configured).",
        }
    order = _provider.get_order(order_id)
    if order is None:
        return {"order_id": order_id, "configured": True, "found": False}
    return {
        "order_id": order_id,
        "configured": True,
        "found": True,
        "order_status": order.get("order_status"),
        "fulfillment_channel": order.get("fulfillment_channel"),
    }


@mcp.tool()
def get_tracking(order_id: str) -> dict:
    """Get shipment tracking info for an Amazon order.

    AmazonOrderProvider's normalization (see
    app/services/providers/amazon/order_provider.py: `_normalize_order`)
    does not extract package/tracking data out of the SP-API response —
    only order status and basic fields. Reports that honestly rather than
    fabricating a tracking number.
    """
    if not _provider.is_configured:
        return {
            "order_id": order_id,
            "configured": False,
            "reason": "Amazon SP-API credentials not configured (see AmazonOrderProvider.is_configured).",
        }
    order = _provider.get_order(order_id)
    if order is None:
        return {"order_id": order_id, "configured": True, "found": False}
    return {
        "order_id": order_id,
        "configured": True,
        "found": True,
        "tracking_available": False,
        "reason": "AmazonOrderProvider does not parse package/tracking data out of the SP-API response.",
        "order_status": order.get("order_status"),
    }


@mcp.tool()
def create_order(
    sku: str,
    quantity: int,
    shipping_address: str,
    customer_name: str,
    product_name: str,
    organization_id: str,
    asin: str | None = None,
) -> dict:
    """Create a fulfillment order and start the existing approval-gated workflow.

    Does NOT execute a supplier submission directly — this calls
    app.services.order_service.create then
    app.services.fulfillment.workflow.fulfillment_engine.start_workflow,
    the same pipeline every order in this system goes through (inventory
    check, address validation, human approval before any submission).
    Returns status="pending_approval" whenever the workflow reaches
    WAITING_APPROVAL; nothing is ever auto-approved from this tool.

    organization_id/customer_name/product_name are required even though the
    minimal (sku, qty, shipping_address) signature might suggest otherwise:
    order creation in this codebase is always tenant-scoped (no default/
    system organization exists — see app/services/order_service.py) and
    customer_name/product_name are non-empty-required fields on the
    underlying order (see app/schemas/order.py). Nothing here invents
    defaults for them.

    asin is optional and written straight through to Order.asin (see
    app/models.py). When set, the fulfillment workflow's price safety-gate
    (_step_check_price_guard) uses it directly — top priority, ahead of
    the SKU-mapping fallback that TikTok-sourced orders use. Omitting it
    is safe: the workflow reports the price check as "not applicable"
    rather than blocking an order this tool wasn't given an ASIN for.
    """
    try:
        org_uuid = UUID(organization_id)
    except ValueError:
        return {"status": "error", "reason": f"Invalid organization_id: {organization_id!r}"}

    try:
        order = order_service.create(
            OrderCreate(
                customer_name=customer_name,
                shipping_address=shipping_address,
                product_name=product_name,
                sku=sku,
                asin=asin,
                quantity=quantity,
                source="MANUAL",
            ),
            org_uuid,
        )
    except Exception as e:
        return {"status": "error", "reason": str(e)}

    workflow = fulfillment_engine.start_workflow(order.id)

    if workflow.status == FulfillmentStatus.WAITING_APPROVAL:
        return {
            "status": "pending_approval",
            "order_id": str(order.id),
            "workflow_id": str(workflow.id),
            "approval_request_id": (
                str(workflow.approval_request_id) if workflow.approval_request_id else None
            ),
            "approval_expires_at": (
                workflow.approval_expires_at.isoformat() if workflow.approval_expires_at else None
            ),
        }
    if workflow.status == FulfillmentStatus.FAILED:
        return {
            "status": "failed",
            "order_id": str(order.id),
            "workflow_id": str(workflow.id),
            "error": workflow.error_message,
        }
    return {
        "status": workflow.status.value,
        "order_id": str(order.id),
        "workflow_id": str(workflow.id),
    }


if __name__ == "__main__":
    mcp.run()
