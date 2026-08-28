# Idempotency Requirements

## CHUNK 1R — Official API Readiness & Compliance Design

Extends the existing CHUNK 1Q idempotency design for a future Amazon provider.

---

## Idempotency Points

| Operation | Idempotency Key | Protection |
|-----------|----------------|------------|
| Amazon Order Import | Amazon Order ID | Skip if already imported |
| Internal Order Creation | Amazon Order ID (external ref) | Skip if already exists |
| Fulfillment Workflow Start | Order ID | Return existing workflow |
| Inventory Reservation | Order ID | Skip if already reserved |
| Supplier Order Submission | Workflow ID | Skip if already submitted |
| Shipment Confirmation | Amazon Order ID + Tracking | Skip if already confirmed |

---

## Duplicate Amazon Import Prevention

```python
def import_amazon_orders(self) -> dict:
    """Import Amazon orders with dedup."""
    # Check: is this Amazon order already imported?
    if amazon_order_id in self._imported_orders:
        # Skip — already imported
        audit("IMPORT_DUPLICATE_BLOCKED", amazon_order_id)
        continue
    
    # Check: does internal order already exist?
    existing = find_by_external_ref(amazon_order_id)
    if existing:
        # Skip — already mapped
        audit("ORDER_DUPLICATE_BLOCKED", amazon_order_id)
        continue
    
    # Import
    ...
```

---

## Duplicate Fulfillment Prevention

Already implemented in CHUNK 1Q:

1. **`FulfillmentWorkflowEngine.start_workflow()`** — returns existing workflow if active
2. **`MockAmazonService.start_fulfillment()`** — checks `_fulfillment_map` before creating
3. **Supplier submission** — blocked if confirmation already exists
4. **Inventory reservation** — skipped if already reserved

---

## External Reference ID

Each internal order should store an external reference ID:

```python
class Order(BaseModel):
    # ... existing fields ...
    external_ref: str | None = Field(None, description="External reference ID (e.g., Amazon Order ID)")
```

This enables:
1. Dedup by external reference
2. Lookup by Amazon Order ID
3. Audit trail linking

---

## Key Principle

**Every operation that creates or modifies state must be idempotent.**

Running the same operation twice should produce the same result as running it once.
