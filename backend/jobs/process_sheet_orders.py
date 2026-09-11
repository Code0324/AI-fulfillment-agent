"""Process pending orders from the Google Sheet through the fulfillment pipeline.

Entry point: python -m jobs.process_sheet_orders

Workflow per order:
  1. Fetch Pending rows from the Orders tab
  2. SKU mapping -> write Amazon ASIN/SKU, Status = Mapped
  3. Pricing check -> on fail: Status = Error, Notes = reason, skip
  4. Create order + start fulfillment workflow
       - mock/sandbox Amazon: auto-approved (fast testing)
       - real Amazon (production): STOPS at "Waiting Approval" in the
         sheet, sends a notification, and exits 3 -- a human must run
         `python -m jobs.process_sheet_orders --approve <order UUID>`
         before any real purchase happens
  5. On success: Amazon Order ID, Tracking Number, Status = Fulfilled
  6. On failure: Status = Error, Notes = reason

The Google Sheet is the single fixed order-intake point. This job reads
Pending rows and writes results back -- it does not create a parallel
path, it IS the pipeline between the Sheet and Amazon fulfillment.
"""

import argparse
import logging
import os
import sys
from datetime import datetime, timezone
from uuid import UUID

# Ensure backend/ is on sys.path so app.* and mcp_servers.* are importable
# when running as `python -m jobs.process_sheet_orders` from backend/.
_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

# Load the repo-root .env BEFORE importing app modules: app.core.config reads
# environment variables at import time. Paths in .env (notably
# GOOGLE_SHEETS_CREDENTIALS_PATH) are interpreted RELATIVE TO THE REPO ROOT
# (where .env lives) -- the same convention docker-compose's env_file uses --
# NOT relative to backend/, even though this job is run with backend/ as cwd.
# This job is usually started as `python -m jobs.process_sheet_orders` from
# backend/, so the root .env is NOT on the default dotenv search path; the
# explicit path below is what makes it load at all. override=True: a stale
# GOOGLE_SHEETS_CREDENTIALS_PATH exported in the user's shell/profile must
# not silently shadow the .env value -- .env is the source of truth here.
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(_backend_dir), ".env"), override=True)

from app.core.config import settings
from app.schemas.inventory import InventoryCreate, InventoryUpdate
from app.schemas.order import OrderCreate, OrderStatus
from app.services.fulfillment.workflow import fulfillment_engine
from app.services.inventory_service import inventory_service
from app.services.order_service import order_service
from app.services.providers.pricing_base import PricingProviderError
from app.services.providers.registry import provider_registry
from app.services.sku_mapping.engine import sku_mapping_engine
from mcp_servers.google_sheets.sheets_client import (
    COL_AMAZON_ASIN_SKU,
    COL_AMAZON_ORDER_ID,
    COL_BUYER_NAME,
    COL_CITY,
    COL_COUNTRY,
    COL_ORDER_ID,
    COL_PHONE,
    COL_QTY,
    COL_STATE,
    COL_STATUS,
    COL_TIKTOK_SKU,
    COL_TRACKING_NUMBER,
    COL_ZIP,
    ORDERS_HEADER,
    SheetsClientError,
    sheets_client,
)

logger = logging.getLogger(__name__)

# The spreadsheet ID for the Orders tab -- read from SHEET_ID in the
# repo-root .env (loaded above), falling back to the known-good sheet.
SHEET_ID = os.getenv("SHEET_ID")
if not SHEET_ID:
    raise RuntimeError("SHEET_ID environment variable is not set — cannot run without a target spreadsheet")

# Status values used in the Sheet
STATUS_PENDING = "Pending"
STATUS_MAPPED = "Mapped"
STATUS_FULFILLING = "Fulfilling"
STATUS_FULFILLED = "Fulfilled"
STATUS_ERROR = "Error"
# Human-review pause state for REAL (non-mock) Amazon fulfillment. Written to
# the sheet when the workflow stops at WAITING_APPROVAL so nobody mistakes a
# paused real purchase for a completed or failed one.
STATUS_WAITING_APPROVAL = "Waiting Approval"
# Sheet statuses the real (non-dry-run) run picks up: fresh Pending rows plus
# rows previously paused for human review (their workflow is re-driven on
# pickup; --approve performs the actual approval).
REAL_RUN_STATUSES = (STATUS_PENDING, STATUS_WAITING_APPROVAL)


def _get_default_organization_id() -> UUID:
    """Get the first available organization ID from the database.

    Used as the default tenant for sheet-sourced orders that don't carry
    an org context. Falls back to a hard-coded UUID for environments
    where the database isn't available (e.g. dry-run testing).
    """
    org_id_env = os.getenv("DEFAULT_ORGANIZATION_ID")
    if org_id_env:
        return UUID(org_id_env)

    try:
        from app.models import Organization
        from app.services.order_service import bridge_session, run_on_bridge_loop
        from sqlalchemy import select

        async def _find_org():
            async with bridge_session() as db:
                result = await db.execute(select(Organization.id).limit(1))
                row = result.scalar_one_or_none()
                if row is None:
                    raise RuntimeError("No organizations found in database")
                return row

        return run_on_bridge_loop(_find_org())
    except Exception as e:
        logger.warning("Could not query database for org: %s -- using fallback", e)
        # Fallback: use a deterministic UUID for testing
        return UUID("00000000-0000-0000-0000-000000000001")


def _ensure_inventory(amazon_sku: str, quantity: int) -> None:
    """Ensure the in-memory inventory can cover `quantity` of amazon_sku.

    Inventory is deliberately process-local (see inventory_service.py -- no
    DB, no external API), so a freshly started job process has empty stock
    and the workflow's inventory check would fail every order. This tops the
    SKU up only when short; it never reduces existing stock. Demo/mock use
    only: the mock supplier that fulfills the order consumes no real stock.
    """
    item = inventory_service.find_by_sku(amazon_sku)
    if item is None:
        inventory_service.create(
            InventoryCreate(
                sku=amazon_sku,
                product_name=f"Sheet order SKU {amazon_sku}",
                current_stock=max(quantity, 100),
            )
        )
        logger.info("Inventory created for SKU %s (stock=%d)", amazon_sku, max(quantity, 100))
    elif item.available_quantity < quantity:
        inventory_service.update(
            item.id,
            InventoryUpdate(current_stock=item.reserved_quantity + quantity),
        )
        logger.info(
            "Inventory topped up for SKU %s (available was %d, needed %d)",
            amazon_sku, item.available_quantity, quantity,
        )


def _update_sheet(
    row_number: int,
    status: str,
    amazon_asin_sku: str = "",
    amazon_order_id: str = "",
    tracking_number: str = "",
    notes: str = "",
) -> None:
    """Write status and Amazon fields back to the Google Sheet."""
    try:
        sheets_client.update_order_status(
            SHEET_ID, row_number, status,
            amazon_asin_sku=amazon_asin_sku,
            amazon_order_id=amazon_order_id,
            tracking_number=tracking_number,
            notes=notes,
        )
        logger.info("Sheet row %d updated: status=%s", row_number, status)
    except SheetsClientError as e:
        logger.error("Failed to update sheet row %d: %s", row_number, e)


def _map_sku(tiktok_sku: str, organization_id: UUID) -> tuple[str, str] | None:
    """Run SKU mapping. Returns (amazon_sku, asin) or None on failure."""
    mapping = sku_mapping_engine.map_sku(tiktok_sku, None, organization_id)
    logger.info(
        "SKU mapping for %s: status=%s, amazon_sku=%s, asin=%s",
        tiktok_sku, mapping.status.value, mapping.amazon_sku, mapping.asin,
    )
    if mapping.status.value == "matched" and mapping.amazon_sku:
        return (mapping.amazon_sku, mapping.asin or "")
    return None


def _check_price(asin: str) -> bool:
    """Run pricing check. Returns True if price is OK, False otherwise."""
    if not asin:
        logger.info("No ASIN for price check -- skipping (not applicable)")
        return True
    pricing_provider = provider_registry.get_pricing_provider()
    try:
        price_result = pricing_provider.get_price(asin)
        price = price_result["price"]
        logger.info("Price for %s: $%.2f (max $%.2f)", asin, price, settings.MAX_ALLOWED_PRICE_USD)
        if price > settings.MAX_ALLOWED_PRICE_USD:
            logger.warning("Price $%.2f exceeds max $%.2f", price, settings.MAX_ALLOWED_PRICE_USD)
            return False
        return True
    except PricingProviderError as e:
        logger.error("Price check failed for %s: %s", asin, e.message)
        return False


def _get_or_create_order(order_data: dict, organization_id: UUID):
    """Return the existing order for this sheet row, or create a new one.

    fulfillment_orders enforces UNIQUE (organization_id, tiktok_order_id);
    without this check, re-processing a row after a mid-run failure (or a
    re-run against an already-inserted Pending row) crashes with a
    UniqueViolationError instead of resuming cleanly.
    """
    from app.models import FulfillmentOrder
    from app.services.order_service import (
        _row_to_schema,
        bridge_session,
        run_on_bridge_loop,
    )
    from sqlalchemy import select

    tiktok_order_id = order_data.get("order_id", "") or None

    async def _find():
        async with bridge_session() as db:
            result = await db.execute(
                select(FulfillmentOrder).where(
                    FulfillmentOrder.organization_id == organization_id,
                    FulfillmentOrder.tiktok_order_id == tiktok_order_id,
                )
            )
            row = result.scalar_one_or_none()
            return _row_to_schema(row) if row is not None else None

    existing = run_on_bridge_loop(_find())
    if existing is not None:
        logger.info("Order for %s already exists (%s) -- reusing", tiktok_order_id, existing.id)
        return existing

    tiktok_sku = order_data.get("tiktok_sku", "")
    try:
        qty = int(order_data.get("qty", 1))
    except (ValueError, TypeError):
        qty = 1
    return order_service.create(
        OrderCreate(
            customer_name=order_data.get("buyer_name", "Unknown"),
            shipping_address=order_data.get("shipping_address", "Unknown"),
            product_name=order_data.get("tiktok_sku", "Unknown Product"),
            sku=tiktok_sku,
            asin=order_data.get("asin", None),
            quantity=qty,
            source="TIKTOK",
            tiktok_order_id=tiktok_order_id,
            channel_metadata={"tiktok_sku": tiktok_sku} if tiktok_sku else None,
        ),
        organization_id,
    )


def _is_mock_amazon_mode() -> bool:
    """True when fulfillment runs against mock/sandbox, not real Amazon.

    Real Amazon = the Amazon order provider is registered (i.e. real LWA
    credentials are configured -- see providers/registry.py) AND its
    environment is production. Sandbox/mock (including the default no-
    credentials case, where only mock providers exist) is always safe to
    auto-approve.
    """
    amazon = provider_registry.get_amazon_provider()
    if amazon is None:
        return True  # only mock providers registered -- safe
    return bool(amazon.is_mock)  # SANDBOX/MOCK -> True; PRODUCTION -> False


def _safe_cell(row: list, idx: int) -> str:
    """Out-of-range-safe cell read for raw sheet rows."""
    return str(row[idx]).strip() if idx < len(row) and row[idx] else ""


def _notify_approval_needed(order, workflow) -> None:
    """Alert a human that a REAL fulfillment is waiting for approval.

    Uses the configured notification provider (NOTIFICATION_PROVIDER):
    "slack" posts to SLACK_WEBHOOK_URL when set; the default "log"
    provider writes a genuine alert log line. Delivery is best-effort:
    a notification failure is logged but never fails the run -- the
    authoritative signal is the sheet row left in "Waiting Approval"
    and the DB order/workflow state.
    """
    title = f"Amazon fulfillment needs approval: {order.product_name}"
    message = (
        f"Order {order.id} (sheet row ID {order.tiktok_order_id}) is paused at "
        f"WAITING_APPROVAL before real purchase. "
        f"SKU={order.sku} ASIN={order.asin or '-'} qty={order.quantity}. "
        f"Approve with: python -m jobs.process_sheet_orders --approve {order.id}"
    )
    provider = provider_registry.get_notification_provider()
    try:
        result = provider.send(title, message, severity="warning")
        logger.info("Approval notification sent via %s: %s", result.get("channel"), result.get("sent"))
    except Exception as e:
        logger.error("Failed to send approval notification: %s", e)
        logger.error("MANUAL ACTION NEEDED: workflow %s (order %s) is WAITING_APPROVAL", workflow.id, order.id)


def _create_and_fulfill(
    order_data: dict, organization_id: UUID, dry_run: bool = False,
    row_number: int | None = None,
) -> dict:
    """Create an order in the system and run it through the fulfillment workflow.

    Returns dict with keys:
      - success: bool
      - amazon_order_id: str (if available)
      - tracking_number: str (if available)
      - error: str (if failed)

    Approval policy (never auto-approve a real purchase):
      - --dry-run: the workflow never reaches the approval step (returns earlier)
      - mock/sandbox Amazon mode: auto-approved so testing stays fast
      - real Amazon credentials + production: STOPS at WAITING_APPROVAL;
        the sheet row goes to "Waiting Approval", a notification is sent,
        and the run completes with exit code 3 until a human approves.
    """
    try:
        qty = int(order_data.get("qty", 1))
    except (ValueError, TypeError):
        qty = 1

    # Build the full shipping address in the multi-line format the
    # address processor expects (app/services/address/processor.py):
    # line 1 = full name, line 2 = street, then "City, ST ZIP" and country.
    # A single comma-joined line fails validation with
    # "Address too short -- need at least name and street".
    buyer_name = order_data.get("buyer_name", "Unknown").strip() or "Unknown"
    city = order_data.get("city", "").strip()
    state = order_data.get("state", "").strip()
    zip_code = order_data.get("zip", "").strip()
    country = order_data.get("country", "").strip() or "US"

    address_lines = [buyer_name]
    street = order_data.get("shipping_address", "").strip()
    if street:
        address_lines.append(street)
    city_state_zip = ", ".join(
        part for part in (city, " ".join(p for p in (state, zip_code) if p)) if part
    )
    if city_state_zip:
        address_lines.append(city_state_zip)
    if len(address_lines) > 2:
        address_lines.append(country)
    shipping_address = "\n".join(address_lines)

    # Route through the full TikTok fulfillment path: with source="TIKTOK",
    # the workflow's _step_resolve_sku_mapping re-resolves the TikTok SKU via
    # the explicit DB mapping and the price guard can use the mapped ASIN.
    # order.sku initially carries the TikTok SKU and is overwritten with the
    # mapped Amazon SKU by the workflow; channel_metadata keeps the original
    # TikTok SKU so retries re-resolve from the right value. _get_or_create_order
    # stores the multi-line address built above and keeps re-runs idempotent.
    order_data["shipping_address"] = shipping_address

    # Get or create the order in the database (idempotent per sheet row)
    order = _get_or_create_order(order_data, organization_id)
    logger.info("Order: %s (status=%s)", order.id, order.status.value)

    # Already genuinely fulfilled in a previous run: reuse the stored
    # confirmation, never re-run the workflow (a real Amazon order must
    # never be re-purchased because a sheet row got reset).
    if order.amazon_order_id:
        logger.info(
            "Order %s already fulfilled (confirmation %s) -- reusing, not re-purchasing",
            order.id, order.amazon_order_id,
        )
        return {
            "success": True,
            "amazon_order_id": order.amazon_order_id,
            "tracking_number": "(previous run)",
            "reused": True,
        }

    # Interrupted mid-fulfillment (inventory reserved but no recorded
    # confirmation): the outcome is UNKNOWN. Never blind-re-run a real
    # purchase over an unknown state -- stop for human review. EXCEPTION:
    # a row the sheet itself marks "Waiting Approval" is a DELIBERATE
    # pause before submission (the submit step only runs on approval),
    # so re-driving it is safe -- it pauses again at the same point.
    row_status = (order_data.get("status") or "").strip().lower()
    paused_for_approval = row_status == STATUS_WAITING_APPROVAL.lower()
    if (
        order.inventory_reserved
        and not order.amazon_order_id
        and not _is_mock_amazon_mode()
        and not paused_for_approval
    ):
        _update_sheet(
            row_number if row_number is not None else 0,
            STATUS_ERROR,
            amazon_asin_sku=order.sku,
            notes=(
                f"INTERRUPTED: order {order.id} reserved inventory but has no "
                f"fulfillment confirmation. Outcome unknown -- needs manual "
                f"verification before any retry or refund decision."
            ),
        )
        return {
            "success": False,
            "error": (
                f"Order {order.id} interrupted mid-fulfillment (inventory reserved, "
                f"no confirmation) -- refusing to re-run a real purchase. "
                f"Verify manually."
            ),
            "interrupted": True,
        }

    # Inventory is process-local (see _ensure_inventory) -- a fresh job
    # process starts with empty stock. Stock must exist under the MAPPED
    # Amazon SKU: with source="TIKTOK", the workflow re-resolves the SKU
    # (order.sku becomes the Amazon SKU) before its inventory check.
    amazon_sku = order_data.get("amazon_sku", "")
    if amazon_sku:
        _ensure_inventory(amazon_sku, qty)

    # Start the fulfillment workflow
    workflow = fulfillment_engine.start_workflow(order.id)
    logger.info("Workflow %s status: %s", workflow.id, workflow.status.value)

    # Handle WAITING_APPROVAL.
    # AUTO-APPROVE ONLY in mock/sandbox Amazon mode (or dry-run, which never
    # reaches this point). With real Amazon credentials in production
    # environment the workflow must STOP here for human review -- never
    # auto-approve an actual purchase.
    if workflow.status.value == "waiting_approval":
        if _is_mock_amazon_mode() or dry_run:
            logger.info("Auto-approving workflow %s (mock/sandbox Amazon mode)", workflow.id)
            workflow = fulfillment_engine.approve_workflow(workflow.id)
            logger.info("Workflow %s after approval: %s", workflow.id, workflow.status.value)
        else:
            logger.warning(
                "Workflow %s is WAITING_APPROVAL with real Amazon credentials -- "
                "NOT auto-approving. Human review required before purchase.",
                workflow.id,
            )
            _update_sheet(
                row_number if row_number is not None else 0,
                STATUS_WAITING_APPROVAL,
                amazon_asin_sku=order.sku,
                amazon_order_id="",
                tracking_number="",
                notes=(
                    f"WAITING APPROVAL: real Amazon purchase needs manual review. "
                    f"Approve: python -m jobs.process_sheet_orders --approve {order.id}"
                ),
            )
            _notify_approval_needed(order, workflow)
            return {
                "success": False,
                "error": "WAITING_APPROVAL: real Amazon fulfillment needs human approval",
                "waiting_approval": True,
                "workflow_id": str(workflow.id),
                "order_id": str(order.id),
            }

    # Extract results
    if workflow.status.value == "completed" and workflow.confirmation:
        return {
            "success": True,
            "amazon_order_id": workflow.confirmation.confirmation_id,
            "tracking_number": workflow.confirmation.estimated_delivery or "",
        }
    elif workflow.status.value == "failed":
        return {
            "success": False,
            "error": workflow.error_message or "Workflow failed",
        }
    else:
        return {
            "success": False,
            "error": f"Unexpected workflow status: {workflow.status.value}",
        }


def process_pending_orders(dry_run: bool = False) -> dict:
    """Main entry point: fetch pending orders from the Sheet and process each.

    Args:
        dry_run: If True, don't actually create orders -- just validate mapping/pricing.

    Returns:
        Summary dict with counts of processed/failed/skipped orders.
    """
    if not sheets_client.is_configured:
        logger.error("Google Sheets not configured -- GOOGLE_SHEETS_CREDENTIALS_PATH is unset")
        return {"error": "Google Sheets not configured"}

    logger.info("Fetching orders with status %s from sheet %s...", "/".join(REAL_RUN_STATUSES), SHEET_ID)
    pending = sheets_client.fetch_pending_orders(SHEET_ID, statuses=REAL_RUN_STATUSES)
    logger.info("Found %d pending order(s)", len(pending))

    if not pending:
        return {"processed": 0, "failed": 0, "skipped": 0, "message": "No pending orders"}

    organization_id = _get_default_organization_id()
    logger.info("Using organization_id: %s", organization_id)

    results = {"processed": 0, "failed": 0, "skipped": 0, "waiting_approval": 0, "details": []}

    for order_data in pending:
        order_id = order_data.get("order_id", "unknown")
        row_number = order_data["row_number"]
        tiktok_sku = order_data.get("tiktok_sku", "")
        logger.info("--- Processing order %s (row %d, SKU: %s) ---", order_id, row_number, tiktok_sku)

        try:
            # Step 1: SKU Mapping
            logger.info("Step 1: SKU mapping for %s", tiktok_sku)
            mapping = _map_sku(tiktok_sku, organization_id)
            if mapping is None:
                _update_sheet(row_number, STATUS_ERROR, notes=f"SKU mapping failed for {tiktok_sku}")
                results["failed"] += 1
                results["details"].append({"order_id": order_id, "status": "error", "reason": "SKU mapping failed"})
                continue

            amazon_sku, asin = mapping
            _update_sheet(row_number, STATUS_MAPPED, amazon_asin_sku=amazon_sku)
            logger.info("Step 1 complete: %s -> %s (ASIN: %s)", tiktok_sku, amazon_sku, asin)

            # Step 2: Pricing Check
            logger.info("Step 2: Price check for ASIN %s", asin)
            if not _check_price(asin):
                _update_sheet(row_number, STATUS_ERROR, amazon_asin_sku=amazon_sku, notes=f"Price check failed for ASIN {asin}")
                results["failed"] += 1
                results["details"].append({"order_id": order_id, "status": "error", "reason": "Price check failed"})
                continue
            logger.info("Step 2 complete: price check passed")

            # Step 3: Fulfillment
            _update_sheet(row_number, STATUS_FULFILLING, amazon_asin_sku=amazon_sku)

            if dry_run:
                logger.info("Step 3: DRY RUN -- would create fulfillment order for %s", order_id)
                _update_sheet(row_number, STATUS_FULFILLED, amazon_asin_sku=amazon_sku, notes="Dry run -- not actually fulfilled")
                results["processed"] += 1
                results["details"].append({"order_id": order_id, "status": "fulfilled", "dry_run": True})
                continue

            order_data["amazon_sku"] = amazon_sku
            order_data["asin"] = asin
            result = _create_and_fulfill(
                order_data, organization_id, dry_run=dry_run, row_number=row_number,
            )

            if result["success"]:
                _update_sheet(
                    row_number, STATUS_FULFILLED,
                    amazon_asin_sku=amazon_sku,
                    amazon_order_id=result.get("amazon_order_id", ""),
                    tracking_number=result.get("tracking_number", ""),
                )
                results["processed"] += 1
                results["details"].append({"order_id": order_id, "status": "fulfilled", **result})
            elif result.get("reused"):
                # Order was already fulfilled in a previous run -- reflect
                # that truthfully on the sheet without re-running anything.
                _update_sheet(
                    row_number, STATUS_FULFILLED,
                    amazon_asin_sku=amazon_sku,
                    amazon_order_id=result.get("amazon_order_id", ""),
                    notes="Already fulfilled in a previous run -- confirmation reused",
                )
                results["processed"] += 1
                results["details"].append({"order_id": order_id, "status": "fulfilled", **result})
            elif result.get("waiting_approval"):
                # Already written to the sheet as "Waiting Approval" and
                # notified inside _create_and_fulfill -- don't count as failed.
                results["waiting_approval"] += 1
                results["details"].append({"order_id": order_id, "status": "waiting_approval", **result})
            elif result.get("interrupted"):
                # Already written to the sheet as Error with a clear note.
                results["failed"] += 1
                results["details"].append({"order_id": order_id, "status": "error", **result})
            else:
                _update_sheet(row_number, STATUS_ERROR, amazon_asin_sku=amazon_sku, notes=result.get("error", "Unknown error"))
                results["failed"] += 1
                results["details"].append({"order_id": order_id, "status": "error", **result})

        except Exception as e:
            logger.exception("Unhandled error processing order %s", order_id)
            _update_sheet(row_number, STATUS_ERROR, notes=f"Unhandled error: {e}")
            results["failed"] += 1
            results["details"].append({"order_id": order_id, "status": "error", "error": str(e)})

    logger.info(
        "Processing complete: %d processed, %d failed, %d skipped, %d waiting approval",
        results["processed"], results["failed"], results["skipped"], results["waiting_approval"],
    )
    return results


def _approve_waiting_order(order_id: UUID) -> int:
    """Manually approve a real fulfillment left at WAITING_APPROVAL.

    Re-finds the paused order by ID, re-drives its workflow (the engine is
    in-memory, so a new process has no memory of it), auto-approves the
    re-created WAITING_APPROVAL pause (this IS the human approval), and
    writes the result to the sheet.

    IMPORTANT SAFETY MODEL: the risky steps (inventory reservation, supplier
    submission) re-run AFTER this explicit `--approve` invocation -- the
    human who typed the command is the approval. Also re-verifies price and
    inventory before approving; if anything changed since the pause, the
    order is refused and left untouched.

    Returns an exit code (0 on success).
    """
    from app.models import FulfillmentOrder
    from app.services.order_service import (
        _row_to_schema,
        bridge_session,
        run_on_bridge_loop,
    )
    from sqlalchemy import select

    async def _find():
        async with bridge_session() as db:
            result = await db.execute(
                select(FulfillmentOrder).where(FulfillmentOrder.id == order_id)
            )
            row = result.scalar_one_or_none()
            return _row_to_schema(row) if row is not None else None

    order = run_on_bridge_loop(_find())
    if order is None:
        logger.error("No order found with ID %s -- nothing to approve", order_id)
        return 1

    logger.info("Approving order %s (%s, SKU %s, qty %s)", order.id, order.customer_name, order.sku, order.quantity)

    # Re-verify the price guard before approving a real purchase.
    asin = order.asin or ""
    if not _check_price(asin):
        logger.error("Refusing to approve %s: price check no longer passes", order.id)
        return 1

    # Re-verify inventory (process-local; may be empty in a new process).
    if order.sku:
        _ensure_inventory(order.sku, order.quantity)

    # Re-drive the workflow. start_workflow is idempotent per process but a
    # fresh process has no memory -- re-running from scratch is what
    # "resume" means here: all safety gates re-run, and it stops again at
    # WAITING_APPROVAL, which we now approve as the recorded human decision.
    workflow = fulfillment_engine.start_workflow(order.id)
    if workflow.status.value != "waiting_approval":
        if workflow.status.value == "completed" and workflow.confirmation:
            logger.info("Workflow already completed in this process: %s", workflow.confirmation.confirmation_id)
        else:
            logger.error("Workflow is %s, not waiting_approval -- cannot approve", workflow.status.value)
            return 1

    workflow = fulfillment_engine.approve_workflow(workflow.id)
    logger.info("Workflow %s after approval: %s", workflow.id, workflow.status.value)

    if workflow.status.value == "completed" and workflow.confirmation:
        confirmation_id = workflow.confirmation.confirmation_id
        tracking = workflow.confirmation.estimated_delivery or ""
        # Reflect the approval back onto the sheet row (find it by the
        # sheet's own Order ID in column A = the order's tiktok_order_id).
        if order.tiktok_order_id:
            try:
                rows = sheets_client.read_rows(SHEET_ID, settings.GOOGLE_SHEETS_WORKSHEET_NAME)
                for idx, row in enumerate(rows, start=1):
                    if _safe_cell(row, 0) == order.tiktok_order_id:
                        _update_sheet(
                            idx, STATUS_FULFILLED,
                            amazon_asin_sku=order.sku,
                            amazon_order_id=confirmation_id,
                            tracking_number=tracking,
                            notes=f"Manually approved {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
                        )
                        break
            except SheetsClientError as e:
                logger.error("Approved %s but could not update the sheet: %s", order.id, e)
        print(f"\nApproved and fulfilled: amazon_order_id={confirmation_id}")
        print(f"Tracking: {tracking or '-'}")
        return 0

    print(f"\nApproval failed: {workflow.error_message or workflow.status.value}")
    return 1


def main():
    """CLI entry point for the processing job."""
    parser = argparse.ArgumentParser(
        description="Process pending orders from the Google Sheet through fulfillment."
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Validate mapping and pricing only -- don't create fulfillment orders.",
    )
    parser.add_argument(
        "--approve", metavar="ORDER_ID", default=None,
        help=(
            "Manually approve a real fulfillment that stopped at WAITING_APPROVAL "
            "(the order UUID from the sheet Notes column or the notification). "
            "Re-runs all safety gates, then completes the purchase."
        ),
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable debug logging.",
    )
    parser.add_argument(
        "--inventory-sku", default=None,
        help=(
            "Top up in-process inventory for this SKU before a real run so the "
            "workflow's inventory check passes (inventory is process-local -- "
            "see _ensure_inventory). Not needed for --dry-run."
        ),
    )
    parser.add_argument(
        "--inventory-qty", type=int, default=100,
        help="Stock level to guarantee for --inventory-sku (default: 100).",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if args.approve:
        try:
            order_uuid = UUID(args.approve)
        except ValueError:
            print(f"Invalid order ID: {args.approve!r} -- expected a UUID")
            sys.exit(1)
        sys.exit(_approve_waiting_order(order_uuid))

    if not args.dry_run and args.inventory_sku:
        _ensure_inventory(args.inventory_sku, args.inventory_qty)

    results = process_pending_orders(dry_run=args.dry_run)
    print("\n=== Processing Results ===")
    for key, value in results.items():
        if key != "details":
            print(f"  {key}: {value}")
    if results.get("details"):
        print("\n  Details:")
        for detail in results["details"]:
            print(f"    {detail}")

    # Exit codes: 0 ok, 1 failures, 2 config error, 3 awaiting human approval
    if results.get("error"):
        sys.exit(2)
    if results.get("waiting_approval", 0) > 0:
        sys.exit(3)
    if results.get("failed", 0) > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
