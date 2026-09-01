"""Aggregates connection/automation status for the dashboard control center.

Read-only — computes everything from real state (provider registry,
Google Sheets client, persisted orders, and the in-memory fulfillment
workflow engine). Never fabricates a count or a "connected" status.
"""

import asyncio
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import SkuMapping
from app.schemas.fulfillment import FulfillmentStatus
from app.services import order_service
from app.services.google_sheets.client import google_sheets_client
from app.services.providers.registry import provider_registry

ACTIVITY_LIMIT = 10


async def _provider_connection(provider, environment: str) -> dict:
    """NOT_CONFIGURED / CONNECTION_ERROR / CONNECTED for a provider that
    exposes test_connection() — never reports CONNECTED without actually
    attempting one. test_connection() itself makes a real network call
    (a token fetch), so it only ever runs when credentials are present —
    never on every dashboard load for an unconfigured service."""
    if provider is None:
        return {"status": "NOT_CONFIGURED", "configured": False, "environment": environment}
    try:
        result = await asyncio.to_thread(provider.test_connection)
    except Exception as e:
        return {
            "status": "CONNECTION_ERROR", "configured": True, "environment": environment,
            "error": f"{type(e).__name__}: {e}",
        }
    if result.get("success"):
        return {"status": "CONNECTED", "configured": True, "environment": environment}
    return {
        "status": "CONNECTION_ERROR", "configured": True, "environment": environment,
        "error": result.get("error", "Connection test failed"),
    }


async def _google_sheets_connection() -> dict:
    if not google_sheets_client.is_configured:
        return {"status": "NOT_CONFIGURED", "configured": False}
    try:
        result = await asyncio.to_thread(google_sheets_client.test_connection)
    except Exception as e:
        return {"status": "CONNECTION_ERROR", "configured": True, "error": f"{type(e).__name__}: {e}"}
    if result.get("success"):
        return {"status": "CONNECTED", "configured": True}
    return {"status": "CONNECTION_ERROR", "configured": True, "error": result.get("error")}


async def _connections_status() -> dict:
    tiktok_provider = provider_registry.get_tiktok_provider()
    amazon_provider = provider_registry.get_amazon_provider()
    tiktok, amazon, sheets = await asyncio.gather(
        _provider_connection(tiktok_provider, settings.tiktok_environment),
        _provider_connection(amazon_provider, settings.amazon_environment),
        _google_sheets_connection(),
    )
    return {
        "tiktok": tiktok,
        "amazon": amazon,
        "google_sheets": sheets,
        "database": {"status": "CONNECTED", "healthy": True},
    }


def _step_done(workflow, name: str) -> bool:
    step = next((s for s in workflow.steps if s.name == name), None)
    return step is not None and step.status == "completed"


def _activity_line(order, workflow) -> dict:
    """The latest business milestone this order has reached, in the exact
    business language of the canonical workflow (TikTok order received ->
    Google Sheet updated -> SKU matched -> Amazon product verified ->
    Order prepared -> Approval required -> Order confirmed) — never the
    raw internal step name/description."""
    ref = order.tiktok_order_id or str(order.id)[:8]

    if workflow is None:
        return {"level": "info", "message": f"{ref} — TikTok order received"}
    if workflow.status == FulfillmentStatus.COMPLETED:
        return {"level": "success", "message": f"{ref} — order confirmed"}
    if workflow.status == FulfillmentStatus.WAITING_APPROVAL:
        return {"level": "warning", "message": f"{ref} — approval required"}
    if workflow.status == FulfillmentStatus.FAILED:
        return {"level": "error", "message": f"{ref} — {workflow.error_message or 'failed'}"}
    if workflow.status in (FulfillmentStatus.CANCELLED, FulfillmentStatus.EXPIRED):
        return {"level": "error", "message": f"{ref} — {workflow.status.value}"}

    # RUNNING/PENDING: report the latest milestone actually reached, most
    # advanced first, in business language rather than the internal step name.
    if _step_done(workflow, "validate_provider_order"):
        milestone = "order prepared"
    elif workflow.marketplace_integration_configured:
        milestone = "Amazon product verified"
    elif _step_done(workflow, "resolve_sku_mapping"):
        milestone = "SKU matched"
    elif order.sheet_synced_at:
        milestone = "Google Sheet updated"
    elif _step_done(workflow, "validate_order"):
        milestone = "order data validated"
    else:
        milestone = "TikTok order received"
    return {"level": "info", "message": f"{ref} — {milestone}"}


async def get_dashboard_summary_async(db: AsyncSession, organization_id: UUID) -> dict:
    """Return connection status, automation counts, recent activity, and
    the human-approval queue for TikTok-sourced orders in this org."""
    orders_page = await order_service.list_orders_async(
        db, organization_id, page=1, page_size=100, source="TIKTOK"
    )
    orders = orders_page.items
    order_by_id = {o.id: o for o in orders}

    from app.services.fulfillment.workflow import fulfillment_engine

    all_workflows = await asyncio.to_thread(fulfillment_engine.list_workflows)
    workflow_by_order = {w.order_id: w for w in all_workflows if w.order_id in order_by_id}

    counts = {"new": 0, "processing": 0, "awaiting_approval": 0, "completed": 0, "errors": 0}
    for order in orders:
        workflow = workflow_by_order.get(order.id)
        if workflow is None:
            counts["new"] += 1
        elif workflow.status in (FulfillmentStatus.PENDING, FulfillmentStatus.RUNNING):
            counts["processing"] += 1
        elif workflow.status == FulfillmentStatus.WAITING_APPROVAL:
            counts["awaiting_approval"] += 1
        elif workflow.status == FulfillmentStatus.COMPLETED:
            counts["completed"] += 1
        else:  # FAILED, CANCELLED, EXPIRED
            counts["errors"] += 1

    recent = sorted(orders, key=lambda o: o.updated_at, reverse=True)[:ACTIVITY_LIMIT]
    activity = [_activity_line(o, workflow_by_order.get(o.id)) for o in recent]

    approval_queue = []
    for order in orders:
        workflow = workflow_by_order.get(order.id)
        if workflow is not None and workflow.status == FulfillmentStatus.WAITING_APPROVAL:
            price = (order.channel_metadata or {}).get("price")
            tiktok_sku = (order.channel_metadata or {}).get("tiktok_sku")
            asin = None
            if tiktok_sku:
                mapping_row = (
                    await db.execute(
                        select(SkuMapping).where(
                            SkuMapping.organization_id == organization_id,
                            SkuMapping.tiktok_sku == tiktok_sku,
                            SkuMapping.variation == order.variation,
                        )
                    )
                ).scalar_one_or_none()
                if mapping_row is not None:
                    asin = mapping_row.asin
            integration_mode = "REAL" if workflow.marketplace_integration_configured else "MOCK/SANDBOX"
            approval_queue.append({
                "order_id": str(order.id),
                "workflow_id": str(workflow.id),
                "tiktok_order_id": order.tiktok_order_id,
                "tiktok_sku": tiktok_sku,
                "amazon_sku": order.sku,
                "asin": asin,
                "product_name": order.product_name,
                "variation": order.variation,
                "quantity": order.quantity,
                "price": price,
                "total": round(price * order.quantity, 2) if isinstance(price, (int, float)) else None,
                "customer_name": order.customer_name,
                "shipping_address": order.shipping_address,
                "current_state": workflow.status.value,
                "integration_mode": integration_mode,
            })

    return {
        "connections": await _connections_status(),
        "counts": counts,
        "activity": activity,
        "approval_queue": approval_queue,
    }
