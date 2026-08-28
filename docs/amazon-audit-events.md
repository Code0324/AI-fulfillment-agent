# Amazon Audit Events

## CHUNK 1R — Official API Readiness & Compliance Design

Future audit events required for official Amazon integration.

---

## Amazon-Specific Audit Events

| Event Type | Category | PII? | Description |
|-----------|----------|------|-------------|
| `AMAZON_AUTH_STARTED` | Auth | No | LWA token refresh started |
| `AMAZON_AUTH_COMPLETED` | Auth | No | LWA token refresh completed |
| `AMAZON_AUTH_FAILED` | Auth | No | Authentication failed |
| `AMAZON_API_CALL` | API | No | API call made (operation, status) |
| `AMAZON_API_ERROR` | API | No | API call failed |
| `AMAZON_RATE_LIMITED` | API | No | Rate limit hit |
| `AMAZON_IMPORT_STARTED` | Import | No | Import batch started |
| `AMAZON_ORDER_IMPORTED` | Import | No | Order imported successfully |
| `AMAZON_ORDER_DUPLICATE` | Import | No | Duplicate order skipped |
| `AMAZON_ORDER_MAPPING_FAILED` | Import | No | Order mapping failed |
| `AMAZON_DATA_REDACTED` | Security | No | PII was redacted |
| `AMAZON_PII_ACCESSED` | Security | **YES** | PII was accessed (log redacted) |

---

## Existing Fulfillment Events (Unchanged)

| Event Type | Category | Description |
|-----------|----------|-------------|
| `MOCK_ORDER_IMPORTED` | Import | Mock order imported |
| `ORDER_MAPPED` | Mapping | Order mapped to internal |
| `ADDRESS_PROCESSED` | Address | Address processed |
| `INVENTORY_CHECKED` | Inventory | Inventory checked |
| `INVENTORY_RESERVED` | Inventory | Inventory reserved |
| `FULFILLMENT_STARTED` | Fulfillment | Workflow started |
| `APPROVAL_REQUESTED` | Approval | Approval requested |
| `APPROVAL_APPROVED` | Approval | Approval granted |
| `MOCK_SUPPLIER_SUBMITTED` | Supplier | Supplier order submitted |
| `MOCK_TRACKING_CREATED` | Tracking | Tracking generated |
| `FULFILLMENT_COMPLETED` | Fulfillment | Workflow completed |

---

## Audit Record Format

```python
class AuditEvent(BaseModel):
    id: UUID
    event_type: str
    timestamp: datetime
    details: str  # PII-safe, redacted
    error_message: str | None
    # Amazon-specific (optional)
    amazon_order_id: str | None  # For Amazon events
    api_operation: str | None    # For API events
    api_status_code: int | None  # For API events
```

---

## PII Protection in Audit

1. **Never log PII** in audit details
2. **Apply `redact_pii()`** to all details before storage
3. **Use event types** to categorize — not raw data
4. **Include timestamps** for debugging
5. **Include error messages** for troubleshooting (redacted)

---

## Audit Retention

- **Minimum retention**: 90 days
- **Recommended retention**: 1 year
- **Storage**: Append-only log (no updates, no deletes)
- **Access**: Read-only for authorized users
