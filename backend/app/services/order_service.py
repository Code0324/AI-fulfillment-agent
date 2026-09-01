"""PostgreSQL-backed fulfillment order service.

Real persistence via SQLAlchemy AsyncSession + the FulfillmentOrder model.
Every order belongs to a real, authenticated Organization — there is no
default/system organization, and no client-supplied organization_id is ever
trusted as an authorization source. See app/api/v1/orders.py for how the
organization is derived (JWT -> get_current_user -> get_current_organization).

===========================================================================
TEMPORARY PHASE 2B COMPATIBILITY SEAM (remove in Phase 2C)
===========================================================================
services/fulfillment/workflow.py and services/mock_amazon.py predate this
migration and call this service synchronously, with no event loop of their
own. Converting them to async would cascade through nearly the entire
FulfillmentWorkflowEngine (traced and rejected as out of scope for this
phase — see Phase 2B architectural design report). The `OrderService` class
below is a temporary synchronous facade for exactly those legacy callers.
Do not use this seam for new code — new code should be async and call
create_async/get_async/etc. directly with a request-scoped AsyncSession.

Design (v2 — dedicated bridge loop, not the app's request loop):

The first version of this seam captured the *application's own* event loop
(via a hook in app.main's lifespan) and scheduled bridge coroutines onto it
with `run_coroutine_threadsafe`. That broke under the test suite: several
pre-existing test files each open their own short-lived
`with TestClient(app) as c:` block, which runs (and then tears down) a
*fresh* ASGI lifespan and event loop every time. Every such teardown closed
the loop this module had captured, poisoning it for any later test —
including ones using the shared, still-open session client — with
`RuntimeError: Event loop is closed`.

This version instead runs its own dedicated background event loop, started
lazily on first use and never tied to any particular FastAPI/TestClient
lifespan. It is created exactly once per process and lives until the
process exits, so it is immune to however many times ASGI lifespans start
and stop around it. Bridge coroutines are scheduled onto it the same way as
before, via `asyncio.run_coroutine_threadsafe` — this still only blocks the
*calling* thread, never the loop itself, and never nests a loop inside a
request thread.

The bridge uses its own AsyncEngine (`_bridge_engine`), pointed at the same
PostgreSQL database/schema/ORM models as the application's main engine in
app/database.py — not a second database, not a second ORM, just a second
connection pool. This is deliberate, not incidental: SQLAlchemy's async
engine documentation is explicit that a single AsyncEngine (and its
pooled connections) must not be shared across more than one event loop.
Since the bridge loop and the application's request-handling loop are
different loops, sharing app.database.engine's pool between them risks a
pooled connection created on one loop being checked out and used from the
other, which asyncpg does not support. The bridge engine uses NullPool
(SQLAlchemy's documented recommendation for exactly this multi-loop
scenario) so no connection object ever outlives a single checkout, which
also means it can't be corrupted by whichever loop happens to be active.

Safety properties preserved from v1:
  1. This app runs a single Uvicorn worker / single event loop for its
     *request-handling* path (see backend/Dockerfile's explicit
     "do not add --workers > 1" comment) — the bridge loop is a second,
     dedicated OS thread purely for this legacy seam, not a second worker.
  2. The legacy callers are only ever reached from plain `def` FastAPI route
     handlers (app/api/v1/fulfillment.py, app/api/v1/mock_amazon.py), which
     Starlette dispatches to a threadpool -- never the loop's own thread --
     so scheduling onto a different (bridge) thread/loop is exactly the
     right shape, not a new risk.
  3. No `asyncio.run()` is used anywhere in this module: the bridge loop is
     driven by `run_forever()` on its own thread, and callers only ever
     schedule onto it via `run_coroutine_threadsafe` + `.result()`.
Phase 2C will convert Fulfillment to native async and delete this seam
(the dedicated loop, the bridge engine, and the OrderService class) wholesale.
"""

import asyncio
import threading
from datetime import datetime, timezone
from math import ceil
from uuid import UUID, uuid4

from sqlalchemy import String, cast, delete, func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.errors import NotFoundError, ValidationError
from app.models import FulfillmentOrder
from app.schemas.order import (
    Order,
    OrderCreate,
    OrderListResponse,
    OrderStatus,
)
from app.services.inventory_service import inventory_service

# ---------------------------------------------------------------------------
# Allowed status transitions (unchanged from the previous in-memory service)
# ---------------------------------------------------------------------------

VALID_TRANSITIONS: dict[OrderStatus, list[OrderStatus]] = {
    OrderStatus.PENDING: [OrderStatus.PROCESSING, OrderStatus.CANCELLED],
    OrderStatus.PROCESSING: [OrderStatus.SHIPPED, OrderStatus.CANCELLED],
    OrderStatus.SHIPPED: [OrderStatus.DELIVERED, OrderStatus.CANCELLED],
    OrderStatus.DELIVERED: [],
    OrderStatus.CANCELLED: [],
}


# ---------------------------------------------------------------------------
# Dedicated bridge event loop + engine, for the legacy sync bridge only.
# See the "TEMPORARY PHASE 2B COMPATIBILITY SEAM" section of the module
# docstring for why this exists as a separate loop/engine rather than reusing
# the application's own request-handling loop and engine.
# ---------------------------------------------------------------------------

_bridge_loop: asyncio.AbstractEventLoop | None = None
_bridge_engine = None
_BridgeSessionLocal: async_sessionmaker[AsyncSession] | None = None
_bridge_lock = threading.Lock()


def _ensure_bridge_started() -> asyncio.AbstractEventLoop:
    """Start the dedicated bridge loop/thread/engine on first use (once per
    process) and return the running loop. Thread-safe and idempotent.
    """
    global _bridge_loop, _bridge_engine, _BridgeSessionLocal

    if _bridge_loop is not None:
        return _bridge_loop

    with _bridge_lock:
        if _bridge_loop is not None:  # re-check after acquiring the lock
            return _bridge_loop

        loop = asyncio.new_event_loop()

        def _run_loop_forever() -> None:
            asyncio.set_event_loop(loop)
            loop.run_forever()

        thread = threading.Thread(
            target=_run_loop_forever,
            name="order-service-bridge-loop",
            daemon=True,
        )
        thread.start()

        # Build the bridge's own engine *on* the bridge loop (not this
        # thread) via run_coroutine_threadsafe, so the engine/pool's
        # first-use state is associated with the loop that will actually
        # drive every query against it -- never this (caller's) thread.
        async def _build_engine():
            global _bridge_engine, _BridgeSessionLocal
            _bridge_engine = create_async_engine(
                settings.DATABASE_URL,
                echo=settings.DEBUG,
                poolclass=NullPool,
            )
            _BridgeSessionLocal = async_sessionmaker(
                bind=_bridge_engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
            )

        asyncio.run_coroutine_threadsafe(_build_engine(), loop).result()

        _bridge_loop = loop
        return _bridge_loop


def _run_on_bridge_loop(coro):
    """Run `coro` on the dedicated bridge loop and block the calling thread
    (never the loop) for the result. See the module docstring for why this
    is safe here.
    """
    loop = _ensure_bridge_started()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result()


def run_on_bridge_loop(coro):
    """Public entry point for test infrastructure that needs to run one-off
    async DB setup code repeatedly from a synchronous context -- e.g.
    tests/conftest.py's create_test_organization(). Such code hits the exact
    same cross-event-loop pooled-connection hazard this bridge exists to
    avoid if it instead used asyncio.run() against the application's own
    pooled engine (a fresh asyncio.run() loop each call, sharing one pooled
    engine across many closed-and-reopened loops -- exactly what this
    module's own legacy facade used to do, and exactly what broke it).
    Routing through the same dedicated bridge loop/engine sidesteps that.
    """
    return _run_on_bridge_loop(coro)


def bridge_session() -> AsyncSession:
    """Return a new AsyncSession bound to the dedicated bridge engine, for
    test infrastructure use alongside run_on_bridge_loop(). Must only be
    constructed/used from a coroutine actually running on the bridge loop
    (i.e. inside a coroutine passed to run_on_bridge_loop)."""
    _ensure_bridge_started()
    return _BridgeSessionLocal()


def _row_to_schema(row: FulfillmentOrder) -> Order:
    return Order(
        id=row.id,
        organization_id=row.organization_id,
        customer_name=row.customer_name,
        shipping_address=row.shipping_address,
        product_name=row.product_name,
        sku=row.sku,
        variation=row.variation,
        quantity=row.quantity,
        status=OrderStatus(row.status),
        source=row.source,
        inventory_reserved=row.inventory_reserved,
        tiktok_order_id=row.tiktok_order_id,
        channel_metadata=row.channel_metadata,
        sheet_synced_at=row.sheet_synced_at,
        sheet_sync_error=row.sheet_sync_error,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def _get_row(
    db: AsyncSession, order_id: UUID, organization_id: UUID | None
) -> FulfillmentOrder:
    """Fetch a FulfillmentOrder row by ID.

    organization_id is required for every HTTP-facing call (enforces tenant
    isolation). It is None only for the legacy internal bridge, where the
    caller already possesses the order's UUID from having created/received
    it in a prior, already-authorized step -- the organization returned is
    whatever is genuinely stored on that row, never invented.
    """
    stmt = select(FulfillmentOrder).where(FulfillmentOrder.id == order_id)
    if organization_id is not None:
        stmt = stmt.where(FulfillmentOrder.organization_id == organization_id)
    result = await db.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        raise NotFoundError("Order not found")
    return row


# ---------------------------------------------------------------------------
# Real async implementation -- used directly (awaited) by app/api/v1/orders.py
# ---------------------------------------------------------------------------

async def create_async(
    db: AsyncSession, payload: OrderCreate, organization_id: UUID
) -> Order:
    """Create a new order for a real, authenticated organization.

    organization_id is mandatory -- there is no default/system organization.
    """
    inventory_reserved = False
    if payload.reserve_inventory and payload.sku:
        inventory_service.reserve(payload.sku, payload.quantity)
        inventory_reserved = True

    row = FulfillmentOrder(
        id=uuid4(),
        organization_id=organization_id,
        customer_name=payload.customer_name,
        shipping_address=payload.shipping_address,
        product_name=payload.product_name,
        sku=payload.sku,
        variation=payload.variation,
        quantity=payload.quantity,
        status=payload.status.value,
        source=payload.source,
        inventory_reserved=inventory_reserved,
        tiktok_order_id=payload.tiktok_order_id,
        channel_metadata=payload.channel_metadata,
    )
    db.add(row)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        if inventory_reserved and payload.sku:
            inventory_service.release(payload.sku, payload.quantity)
        raise
    await db.refresh(row)
    return _row_to_schema(row)


async def get_async(
    db: AsyncSession, order_id: UUID, organization_id: UUID | None = None
) -> Order:
    row = await _get_row(db, order_id, organization_id)
    return _row_to_schema(row)


async def list_orders_async(
    db: AsyncSession,
    organization_id: UUID,
    *,
    page: int = 1,
    page_size: int = 10,
    status: OrderStatus | None = None,
    search: str | None = None,
    source: str | None = None,
) -> OrderListResponse:
    """List orders for a real, authenticated organization. organization_id
    is mandatory -- listing is always tenant-scoped."""
    stmt = select(FulfillmentOrder).where(
        FulfillmentOrder.organization_id == organization_id
    )
    if status is not None:
        stmt = stmt.where(FulfillmentOrder.status == status.value)
    if source is not None:
        stmt = stmt.where(FulfillmentOrder.source == source)
    if search:
        pattern = f"%{search.lower()}%"
        stmt = stmt.where(
            sa_func.lower(FulfillmentOrder.customer_name).like(pattern)
            | sa_func.lower(FulfillmentOrder.product_name).like(pattern)
            | sa_func.lower(cast(FulfillmentOrder.id, String)).like(pattern)
        )
    stmt = stmt.order_by(FulfillmentOrder.created_at.asc())

    count_result = await db.execute(
        select(sa_func.count()).select_from(stmt.order_by(None).subquery())
    )
    total_items = count_result.scalar_one()
    total_pages = ceil(total_items / page_size) if total_items else 0

    start = (page - 1) * page_size
    rows = (
        (await db.execute(stmt.offset(start).limit(page_size))).scalars().all()
    )

    return OrderListResponse(
        items=[_row_to_schema(r) for r in rows],
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
    )


async def update_status_async(
    db: AsyncSession,
    order_id: UUID,
    status: OrderStatus,
    organization_id: UUID | None = None,
) -> Order:
    row = await _get_row(db, order_id, organization_id)
    current_status = OrderStatus(row.status)
    allowed = VALID_TRANSITIONS.get(current_status, [])
    if status not in allowed:
        allowed_labels = [s.value for s in allowed]
        raise ValidationError(
            f"Cannot transition from '{current_status.value}' to '{status.value}'. "
            f"Allowed transitions: {allowed_labels or ['(none — terminal status)']}"
        )

    released_sku = None
    if status == OrderStatus.CANCELLED and row.inventory_reserved and row.sku:
        inventory_service.release(row.sku, row.quantity)
        released_sku = row.sku
        row.inventory_reserved = False
    row.status = status.value
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        if released_sku:
            # Undo the inventory release so state matches the persisted row.
            inventory_service.reserve(released_sku, row.quantity)
        raise
    await db.refresh(row)
    return _row_to_schema(row)


async def update_sku_async(
    db: AsyncSession, order_id: UUID, sku: str, organization_id: UUID | None = None
) -> Order:
    """Persist a resolved SKU onto an order.

    Used by the fulfillment workflow's SKU-mapping step
    (services/fulfillment/workflow.py) to replace a TikTok SKU with its
    resolved Amazon SKU before inventory reservation, which re-fetches the
    order from the DB rather than trusting an in-memory value.
    """
    row = await _get_row(db, order_id, organization_id)
    if row.inventory_reserved:
        raise ValidationError("Cannot change SKU after inventory has been reserved")
    row.sku = sku
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    await db.refresh(row)
    return _row_to_schema(row)


async def mark_sheet_synced_async(db: AsyncSession, order_id: UUID) -> None:
    """Record that this order's Google Sheet row was just written
    successfully. Called only after a real, successful Sheets API write —
    never speculatively."""
    row = await _get_row(db, order_id, None)
    row.sheet_synced_at = datetime.now(timezone.utc)
    row.sheet_sync_error = None
    await db.commit()


async def mark_sheet_sync_failed_async(db: AsyncSession, order_id: UUID, error: str) -> None:
    """Record that a Google Sheet sync attempt for this order failed, so
    the UI can show a truthful retry-needed state instead of silence."""
    row = await _get_row(db, order_id, None)
    row.sheet_sync_error = error
    await db.commit()


async def reserve_inventory_async(
    db: AsyncSession, order_id: UUID, organization_id: UUID | None = None
) -> Order:
    row = await _get_row(db, order_id, organization_id)
    if row.inventory_reserved:
        raise ValidationError("Inventory already reserved for this order")
    if not row.sku:
        raise ValidationError("Order has no SKU — cannot reserve inventory")
    inventory_service.reserve(row.sku, row.quantity)
    row.inventory_reserved = True
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        inventory_service.release(row.sku, row.quantity)
        raise
    await db.refresh(row)
    return _row_to_schema(row)


async def clear_inventory_reservation_async(
    db: AsyncSession, order_id: UUID, organization_id: UUID | None = None
) -> Order:
    """Mark an order's inventory as no longer reserved (e.g. after release).

    Unlike reserve_inventory_async, this does not touch inventory_service —
    callers are responsible for releasing the inventory itself first.
    """
    row = await _get_row(db, order_id, organization_id)
    row.inventory_reserved = False
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    await db.refresh(row)
    return _row_to_schema(row)


# ---------------------------------------------------------------------------
# Legacy synchronous bridge -- see module docstring.
# Used ONLY by services/fulfillment/workflow.py and services/mock_amazon.py.
# ---------------------------------------------------------------------------


class OrderService:
    """Synchronous facade over the async implementation above, for legacy
    callers that predate this migration. See module docstring."""

    def create(self, payload: OrderCreate, organization_id: UUID) -> Order:
        """Create an order. organization_id is mandatory — there is no
        default/system organization. A caller with no legitimate
        organization context cannot call this (see services/mock_amazon.py's
        import_mock_orders, which now requires one from its caller)."""

        async def _run() -> Order:
            async with _BridgeSessionLocal() as db:
                return await create_async(db, payload, organization_id)

        return _run_on_bridge_loop(_run())

    def get(self, order_id: UUID, organization_id: UUID | None = None) -> Order:
        async def _run() -> Order:
            async with _BridgeSessionLocal() as db:
                return await get_async(db, order_id, organization_id)

        return _run_on_bridge_loop(_run())

    def update_status(
        self,
        order_id: UUID,
        status: OrderStatus,
        organization_id: UUID | None = None,
    ) -> Order:
        async def _run() -> Order:
            async with _BridgeSessionLocal() as db:
                return await update_status_async(db, order_id, status, organization_id)

        return _run_on_bridge_loop(_run())

    def update_sku(
        self, order_id: UUID, sku: str, organization_id: UUID | None = None
    ) -> Order:
        async def _run() -> Order:
            async with _BridgeSessionLocal() as db:
                return await update_sku_async(db, order_id, sku, organization_id)

        return _run_on_bridge_loop(_run())

    def reserve_inventory(
        self, order_id: UUID, organization_id: UUID | None = None
    ) -> Order:
        async def _run() -> Order:
            async with _BridgeSessionLocal() as db:
                return await reserve_inventory_async(db, order_id, organization_id)

        return _run_on_bridge_loop(_run())

    def clear_inventory_reservation(
        self, order_id: UUID, organization_id: UUID | None = None
    ) -> Order:
        async def _run() -> Order:
            async with _BridgeSessionLocal() as db:
                return await clear_inventory_reservation_async(
                    db, order_id, organization_id
                )

        return _run_on_bridge_loop(_run())

    def clear(self) -> None:
        """Delete all orders (used by tests to reset state)."""

        async def _run() -> None:
            async with _BridgeSessionLocal() as db:
                await db.execute(delete(FulfillmentOrder))
                await db.commit()

        _run_on_bridge_loop(_run())


order_service = OrderService()
