"""In-memory fulfillment order service.

Provides basic CRUD-style operations for generic fulfillment orders.
Intentionally has no database, external APIs, or automation —
data lives only for the lifetime of the process.
"""

import math
from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.core.errors import NotFoundError, ValidationError
from app.schemas.order import (
    Order,
    OrderCreate,
    OrderListResponse,
    OrderStatus,
    OrderUpdate,
)

# ---------------------------------------------------------------------------
# Allowed status transitions
# ---------------------------------------------------------------------------
# pending  → processing, cancelled
# processing → shipped, cancelled
# shipped → delivered, cancelled
# delivered → (terminal — no transitions)
# cancelled → (terminal — no transitions)

VALID_TRANSITIONS: dict[OrderStatus, list[OrderStatus]] = {
    OrderStatus.PENDING: [OrderStatus.PROCESSING, OrderStatus.CANCELLED],
    OrderStatus.PROCESSING: [OrderStatus.SHIPPED, OrderStatus.CANCELLED],
    OrderStatus.SHIPPED: [OrderStatus.DELIVERED, OrderStatus.CANCELLED],
    OrderStatus.DELIVERED: [],
    OrderStatus.CANCELLED: [],
}


class OrderService:
    """In-memory store and operations for fulfillment orders."""

    def __init__(self) -> None:
        self._orders: dict[UUID, Order] = {}

    def create(self, payload: OrderCreate) -> Order:
        """Create a new order."""
        now = datetime.now(timezone.utc)
        order = Order(
            id=uuid4(),
            customer_name=payload.customer_name,
            shipping_address=payload.shipping_address,
            product_name=payload.product_name,
            quantity=payload.quantity,
            status=payload.status,
            created_at=now,
            updated_at=now,
        )
        self._orders[order.id] = order
        return order

    def get(self, order_id: UUID) -> Order:
        """Return one order by ID or raise NotFoundError."""
        order = self._orders.get(order_id)
        if order is None:
            raise NotFoundError("Order not found")
        return order

    def list_orders(
        self, *, page: int = 1, page_size: int = 10, status: OrderStatus | None = None
    ) -> OrderListResponse:
        """Return a paginated slice of orders with optional status filter."""
        all_orders = list(self._orders.values())
        if status is not None:
            all_orders = [o for o in all_orders if o.status == status]
        total_items = len(all_orders)
        total_pages = math.ceil(total_items / page_size) if total_items else 0

        start = (page - 1) * page_size
        end = start + page_size
        items = all_orders[start:end]

        return OrderListResponse(
            items=items,
            page=page,
            page_size=page_size,
            total_items=total_items,
            total_pages=total_pages,
        )

    def update_status(self, order_id: UUID, status: OrderStatus) -> Order:
        """Update the status of an existing order with transition validation."""
        order = self.get(order_id)
        allowed = VALID_TRANSITIONS.get(order.status, [])
        if status not in allowed:
            allowed_labels = [s.value for s in allowed]
            raise ValidationError(
                f"Cannot transition from '{order.status.value}' to '{status.value}'. "
                f"Allowed transitions: {allowed_labels or ['(none — terminal status)']}"
            )
        updated = order.model_copy(
            update={
                "status": status,
                "updated_at": datetime.now(timezone.utc),
            }
        )
        self._orders[order_id] = updated
        return updated

    def clear(self) -> None:
        """Remove all orders (used by tests to reset state)."""
        self._orders.clear()


order_service = OrderService()
