"""TikTok Shop order ingestion.

Fetches orders from the real TikTok Shop provider and persists new ones
into FulfillmentOrder (the DB-level UniqueConstraint on
(organization_id, tiktok_order_id) is the actual idempotency guarantee —
see services/providers/tiktok/order_provider.py's docstring). For each
newly created order this also:
  - best-effort syncs the order to Google Sheets (never blocks/fails the
    import if Sheets is unavailable — the failure is recorded on the
    order row, never silently dropped)
  - starts the existing fulfillment workflow, which will itself stop for
    human review/approval exactly where it always has (SKU mapping,
    address validation, the approval gate) — this module does not
    reimplement any of that.

Never fabricates success: if TikTok Shop isn't configured, this returns
immediately with configured=False and touches nothing.
"""

import asyncio
import logging
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.order import OrderCreate, OrderStatus
from app.schemas.tiktok import TikTokOrder
from app.services import order_service
from app.services.google_sheets.client import GoogleSheetsError, google_sheets_client
from app.services.providers.registry import provider_registry

logger = logging.getLogger(__name__)

MAX_ORDERS_PER_SYNC = 50


def _order_to_create_payload(order: TikTokOrder) -> OrderCreate:
    # Line order matters here: services/address/processor.py's MockAddressProcessor
    # expects "First Last" on line 1, the street address on line 2, and a
    # "City, ST ZIP" line searched for starting at line 3 — see its
    # docstring/regex logic. Getting this wrong doesn't corrupt data (the
    # order still saves correctly with channel_metadata as the source of
    # truth), it just means the fulfillment workflow's address-validation
    # step will report NEEDS_REVIEW instead of passing automatically.
    address_lines = [
        order.recipient_name,
        order.address_line_1,
        f"{order.city}, {order.state} {order.zipcode}",
    ]
    if order.phone_number:
        address_lines.append(f"Phone: {order.phone_number}")
    if order.delivery_instructions:
        address_lines.append(f"Delivery instructions: {order.delivery_instructions}")
    # Country must be the LAST line for MockAddressProcessor to pick it up
    # (it only checks the final line). TikTok Shop orders in this codebase
    # are US-marketplace only (see TIKTOK_SHOP_ID/marketplace config).
    address_lines.append("US")

    return OrderCreate(
        customer_name=order.recipient_name,
        shipping_address="\n".join(address_lines),
        product_name=order.product_name,
        sku=order.sku,
        variation=order.variation,
        quantity=order.quantity,
        status=OrderStatus.PENDING,
        source="TIKTOK",
        tiktok_order_id=order.tiktok_order_id,
        channel_metadata={
            # The original TikTok SKU, preserved separately from
            # FulfillmentOrder.sku — see workflow.py's
            # _step_resolve_sku_mapping, which mutates .sku in place to
            # the resolved Amazon SKU once matched. Without this, a retry
            # after that step already succeeded would try to re-resolve
            # the Amazon SKU as if it were still the TikTok SKU.
            "tiktok_sku": order.sku,
            "phone_number": order.phone_number,
            "address_line_1": order.address_line_1,
            "delivery_instructions": order.delivery_instructions,
            "city": order.city,
            "state": order.state,
            "zipcode": order.zipcode,
            "price": order.price,
            "delivery_date": order.delivery_date.isoformat() if order.delivery_date else None,
            "order_date": order.order_date.isoformat(),
            "order_status": order.order_status,
        },
    )


def _empty_result(configured: bool, notice: str, errors: list[str] | None = None) -> dict:
    return {
        "configured": configured,
        "notice": notice,
        "fetched": 0,
        "created": 0,
        "skipped_existing": 0,
        "sheet_synced": 0,
        "sheet_failed": 0,
        "workflow_started": 0,
        "errors": errors or [],
    }


async def sync_tiktok_orders_async(db: AsyncSession, organization_id: UUID) -> dict:
    """Fetch orders from TikTok Shop and persist any that are new.

    Returns a summary dict describing exactly what happened — never
    fabricates a "configured" or "synced" result.
    """
    tiktok_provider = provider_registry.get_tiktok_provider()
    if tiktok_provider is None:
        return _empty_result(
            configured=False,
            notice="TikTok Shop is not configured/authorized — nothing to sync",
        )

    try:
        # get_orders() calls asyncio.run() internally, so it must run off
        # this coroutine's own event loop thread.
        fetched_orders: list[TikTokOrder] = await asyncio.to_thread(
            tiktok_provider.get_orders, limit=MAX_ORDERS_PER_SYNC
        )
    except Exception as e:
        logger.error("TikTok order fetch failed: %s: %s", type(e).__name__, e)
        return _empty_result(
            configured=True,
            notice=f"Failed to fetch orders from TikTok Shop: {type(e).__name__}: {e}",
            errors=[str(e)],
        )

    created = 0
    skipped_existing = 0
    sheet_synced = 0
    sheet_failed = 0
    workflow_started = 0
    errors: list[str] = []

    for tiktok_order in fetched_orders:
        try:
            payload = _order_to_create_payload(tiktok_order)
            new_order = await order_service.create_async(db, payload, organization_id)
            created += 1
        except IntegrityError:
            # DB-level uniqueness on (organization_id, tiktok_order_id) —
            # already imported, this is the real idempotency mechanism.
            skipped_existing += 1
            continue
        except Exception as e:
            logger.error("Failed to persist TikTok order %s: %s", tiktok_order.tiktok_order_id, e)
            errors.append(f"{tiktok_order.tiktok_order_id}: {type(e).__name__}: {e}")
            continue

        if google_sheets_client.is_configured:
            try:
                await asyncio.to_thread(google_sheets_client.sync_order, tiktok_order)
                await order_service.mark_sheet_synced_async(db, new_order.id)
                sheet_synced += 1
            except GoogleSheetsError as e:
                logger.warning("Google Sheets sync failed for order %s: %s", tiktok_order.tiktok_order_id, e)
                await order_service.mark_sheet_sync_failed_async(db, new_order.id, str(e))
                sheet_failed += 1

        try:
            # Sync engine using the legacy bridge internally — must also
            # run off this coroutine's own event loop thread.
            from app.services.fulfillment.workflow import fulfillment_engine

            await asyncio.to_thread(fulfillment_engine.start_workflow, new_order.id)
            workflow_started += 1
        except Exception as e:
            logger.error("Failed to start fulfillment workflow for order %s: %s", new_order.id, e)
            errors.append(f"{tiktok_order.tiktok_order_id}: failed to start fulfillment workflow: {e}")

    return {
        "configured": True,
        "notice": (
            f"Synced {created} new order(s) from TikTok Shop"
            if created
            else "No new orders to sync"
        ),
        "fetched": len(fetched_orders),
        "created": created,
        "skipped_existing": skipped_existing,
        "sheet_synced": sheet_synced,
        "sheet_failed": sheet_failed,
        "workflow_started": workflow_started,
        "errors": errors,
    }
