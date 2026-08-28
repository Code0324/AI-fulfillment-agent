# Amazon Provider Contract

## CHUNK 1S — Amazon Provider Contract + Mock Contract Tests

Defines the provider contract that all order providers must implement.

---

## 1. Provider Responsibilities

Any order provider must:

1. **Return normalized order data** — consistent dict format regardless of source
2. **Prevent duplicate imports** — idempotent by external order ID
3. **Handle errors safely** — raise ProviderError subclasses, not raw exceptions
4. **Stay within provider boundary** — no Amazon-specific types leak to fulfillment engine
5. **Support mock-only mode** — all providers must work without external dependencies

---

## 2. Core Interface

```python
class OrderProvider(BaseProvider):
    @property
    def provider_name(self) -> str: ...

    @property
    def environment(self) -> ProviderEnvironment: ...

    @property
    def capabilities(self) -> ProviderCapabilities: ...

    def get_order(self, order_id: str) -> dict | None: ...
    def list_orders(self, *, limit: int, offset: int) -> list[dict]: ...
    def get_order_count(self) -> int: ...
```

---

## 3. Normalized Data Contract

All providers must return orders in this format:

```python
{
    "order_id": str,          # Provider-specific order ID
    "sku": str,               # Product SKU
    "product_name": str,      # Product name
    "quantity": int,          # Quantity ordered (>= 1)
    "customer_name": str,     # Customer name
    "shipping_address": str,  # Multi-line shipping address
    "status": str,            # Order status
    "created_at": str,        # ISO timestamp
}
```

**Fields NOT required** (provider-specific, not in internal model):
- `source` — provider-specific, stripped at mapping boundary
- `phone` — provider-specific, stripped at mapping boundary
- `external_ref` — provider-specific, stored separately

---

## 4. Error Contract

All provider errors must extend `ProviderError`:

```python
ProviderError                    # Base
├── ProviderUnavailableError    # Provider not available
├── ProviderOperationNotSupportedError  # Operation not supported
├── ProviderValidationError     # Validation failed
├── ProviderSubmissionBlockedError      # Submission blocked
└── ProviderAuthenticationError         # Auth required (should not happen in mock)
```

Each error has:
- `message: str` — human-readable error
- `recoverable: bool` — whether retry is safe

---

## 5. Idempotency Contract

| Operation | Idempotency Key | Behavior |
|-----------|----------------|----------|
| `get_order()` | order_id | Returns same data on repeat calls |
| `list_orders()` | (none) | Returns same list on repeat calls |
| Import | external order ID | Skips already-imported orders |

---

## 6. PII Boundary

Provider data may contain PII (customer name, address) for fulfillment purposes.

But:
1. PII must be redacted in all audit logs via `redact_pii()`
2. PII must not be exposed in error messages
3. PII must not be logged in debug output
4. Provider-specific PII fields (email, phone) should be stripped at mapping boundary

---

## 7. Approval Boundary

Providers are READ-ONLY data sources. They cannot:

1. Submit supplier orders
2. Bypass the approval gate
3. Auto-approve fulfillments
4. Modify Amazon orders
5. Cancel orders

The fulfillment engine controls all external actions through the approval gate.

---

## 8. Mock Behavior

Mock providers (`MockOrderProvider`) return hardcoded synthetic data:

1. No external calls
2. No network requests
3. No credentials required
4. Deterministic responses
5. Safe for parallel testing

---

## 9. Future Amazon Implementation Boundary

A future `AmazonOrderProvider` would:

1. Implement the same `BaseProvider` interface
2. Use SP-API v2026-01-01 (read-only)
3. Transform Amazon responses to normalized dict format
4. Redact PII at the provider boundary
5. Handle rate limits internally
6. Use LWA OAuth for authentication

It would NOT:

1. Make write operations (no confirmShipment, no cancel)
2. Store PII beyond fulfillment needs
3. Bypass the approval gate
4. Call non-Amazon endpoints

---

## 10. Explicitly Forbidden Provider Behavior

| Forbidden | Reason |
|-----------|--------|
| Auto-approve fulfillment | Violates approval gate |
| Bypass inventory validation | Violates safety |
| Skip idempotency checks | Creates duplicates |
| Log PII in audit records | Privacy violation |
| Make external HTTP calls (in mock) | Safety violation |
| Store credentials in code | Security violation |
| Expose Amazon-specific types to fulfillment | Architecture violation |
