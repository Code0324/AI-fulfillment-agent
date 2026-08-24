"""In-memory inventory service.

Provides basic CRUD-style operations for generic inventory items.
Intentionally has no database, external APIs, or automation —
data lives only for the lifetime of the process.
"""

import math
from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.core.errors import NotFoundError, ValidationError
from app.schemas.inventory import (
    InventoryCreate,
    InventoryItem,
    InventoryListResponse,
    InventoryStatus,
    InventoryUpdate,
)


def _compute_status(
    current_stock: int, reserved_quantity: int, low_stock_threshold: int
) -> InventoryStatus:
    """Compute inventory status from quantities."""
    available = current_stock - reserved_quantity
    if available <= 0:
        return InventoryStatus.OUT_OF_STOCK
    if available <= low_stock_threshold:
        return InventoryStatus.LOW_STOCK
    return InventoryStatus.IN_STOCK


class InventoryService:
    """In-memory store and operations for inventory items."""

    def __init__(self) -> None:
        self._items: dict[UUID, InventoryItem] = {}

    def _build_item(
        self,
        *,
        id: UUID,
        sku: str,
        product_name: str,
        current_stock: int,
        reserved_quantity: int,
        low_stock_threshold: int,
        created_at: datetime,
        updated_at: datetime,
    ) -> InventoryItem:
        """Build an InventoryItem with computed fields."""
        available_quantity = current_stock - reserved_quantity
        status = _compute_status(current_stock, reserved_quantity, low_stock_threshold)
        return InventoryItem(
            id=id,
            sku=sku,
            product_name=product_name,
            current_stock=current_stock,
            reserved_quantity=reserved_quantity,
            available_quantity=available_quantity,
            low_stock_threshold=low_stock_threshold,
            status=status,
            created_at=created_at,
            updated_at=updated_at,
        )

    def create(self, payload: InventoryCreate) -> InventoryItem:
        """Create a new inventory item."""
        if payload.reserved_quantity > payload.current_stock:
            raise ValidationError(
                f"Reserved quantity ({payload.reserved_quantity}) cannot exceed "
                f"current stock ({payload.current_stock})"
            )
        now = datetime.now(timezone.utc)
        item = self._build_item(
            id=uuid4(),
            sku=payload.sku,
            product_name=payload.product_name,
            current_stock=payload.current_stock,
            reserved_quantity=payload.reserved_quantity,
            low_stock_threshold=payload.low_stock_threshold,
            created_at=now,
            updated_at=now,
        )
        self._items[item.id] = item
        return item

    def get(self, item_id: UUID) -> InventoryItem:
        """Return one inventory item by ID or raise NotFoundError."""
        item = self._items.get(item_id)
        if item is None:
            raise NotFoundError("Inventory item not found")
        return item

    def list_items(
        self,
        *,
        page: int = 1,
        page_size: int = 10,
        status: InventoryStatus | None = None,
        search: str | None = None,
    ) -> InventoryListResponse:
        """Return a paginated slice of inventory items with optional filters."""
        all_items = list(self._items.values())
        if status is not None:
            all_items = [i for i in all_items if i.status == status]
        if search:
            q = search.lower()
            all_items = [
                i
                for i in all_items
                if q in i.sku.lower()
                or q in i.product_name.lower()
                or q in str(i.id).lower()
            ]
        total_items = len(all_items)
        total_pages = math.ceil(total_items / page_size) if total_items else 0

        start = (page - 1) * page_size
        end = start + page_size
        items = all_items[start:end]

        return InventoryListResponse(
            items=items,
            page=page,
            page_size=page_size,
            total_items=total_items,
            total_pages=total_pages,
        )

    def update(self, item_id: UUID, payload: InventoryUpdate) -> InventoryItem:
        """Update an inventory item with validation."""
        item = self.get(item_id)

        # Apply updates
        new_stock = payload.current_stock if payload.current_stock is not None else item.current_stock
        new_reserved = payload.reserved_quantity if payload.reserved_quantity is not None else item.reserved_quantity
        new_threshold = payload.low_stock_threshold if payload.low_stock_threshold is not None else item.low_stock_threshold

        if new_reserved > new_stock:
            raise ValidationError(
                f"Reserved quantity ({new_reserved}) cannot exceed "
                f"current stock ({new_stock})"
            )

        now = datetime.now(timezone.utc)
        updated = self._build_item(
            id=item.id,
            sku=item.sku,
            product_name=item.product_name,
            current_stock=new_stock,
            reserved_quantity=new_reserved,
            low_stock_threshold=new_threshold,
            created_at=item.created_at,
            updated_at=now,
        )
        self._items[item_id] = updated
        return updated

    def find_by_sku(self, sku: str) -> InventoryItem | None:
        """Return an inventory item by SKU or None if not found."""
        for item in self._items.values():
            if item.sku == sku:
                return item
        return None

    def reserve(self, sku: str, quantity: int) -> InventoryItem:
        """
        Reserve inventory for an order.

        Raises NotFoundError if SKU not found.
        Raises ValidationError if available quantity is insufficient.
        """
        item = self.find_by_sku(sku)
        if item is None:
            raise NotFoundError(f"No inventory item found for SKU '{sku}'")
        if quantity < 1:
            raise ValidationError("Reservation quantity must be at least 1")
        if quantity > item.available_quantity:
            raise ValidationError(
                f"Insufficient inventory for SKU '{sku}': "
                f"requested {quantity}, available {item.available_quantity}"
            )
        new_reserved = item.reserved_quantity + quantity
        return self.update(
            item.id,
            InventoryUpdate(reserved_quantity=new_reserved),
        )

    def release(self, sku: str, quantity: int) -> InventoryItem:
        """
        Release reserved inventory (e.g., on order cancellation).

        Raises NotFoundError if SKU not found.
        Raises ValidationError if quantity exceeds reserved.
        """
        item = self.find_by_sku(sku)
        if item is None:
            raise NotFoundError(f"No inventory item found for SKU '{sku}'")
        if quantity < 1:
            raise ValidationError("Release quantity must be at least 1")
        if quantity > item.reserved_quantity:
            raise ValidationError(
                f"Cannot release {quantity} from SKU '{sku}': "
                f"only {item.reserved_quantity} reserved"
            )
        new_reserved = item.reserved_quantity - quantity
        return self.update(
            item.id,
            InventoryUpdate(reserved_quantity=new_reserved),
        )

    def clear(self) -> None:
        """Remove all inventory items (used by tests to reset state)."""
        self._items.clear()


inventory_service = InventoryService()
