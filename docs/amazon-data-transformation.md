# Amazon Data Transformation Design

## CHUNK 1R — Official API Readiness & Compliance Design

Documents the future transformation from Amazon API responses to internal models.

---

## Transformation Pipeline

```
Amazon SP-API Response (v2026-01-01)
        ↓
Amazon Provider Adapter
        ↓
PII Redaction Layer
        ↓
Validation
        ↓
Internal OrderCreate
        ↓
Existing Order Service
        ↓
Existing Fulfillment Workflow
```

---

## Amazon Response → Internal OrderCreate

### Amazon `searchOrders` Response (Simplified)

```json
{
  "payload": {
    "orders": [
      {
        "amazonOrderId": "111-1234567-1234567",
        "orderStatus": "Unshipped",
        "purchaseDate": "2026-01-15T10:00:00Z",
        "lastUpdateDate": "2026-01-15T10:00:00Z",
        "fulfillmentChannel": "MFN",
        "salesChannel": "Amazon.com",
        "shipServiceLevel": "Standard",
        "orderTotal": { "amount": "29.99", "currencyCode": "USD" },
        "numberOfItemsShipped": 0,
        "numberOfItemsUnshipped": 1,
        "paymentMethod": "GiftBoxBalance",
        "isReplacementOrder": false,
        "isBusinessOrder": false,
        "isPrime": false,
        "isPremiumOrder": false,
        "isGlobalSecureEnabled": false,
        "marketplaceId": "ATVPDKIKX0DER"
      }
    ]
  }
}
```

### Internal `OrderCreate` Schema

```python
class OrderCreate(BaseModel):
    customer_name: str        # From shipping address
    shipping_address: str     # From shipping address (normalized)
    product_name: str         # From order items
    sku: str                  # From order items (SellerSKU)
    quantity: int             # From order items
    status: OrderStatus       # Mapped from Amazon status
    reserve_inventory: bool   # Workflow decision
```

### Field Mapping

| Amazon Field | Internal Field | Transformation |
|-------------|---------------|----------------|
| `amazonOrderId` | Not stored directly | Used as external reference ID |
| `orderStatus` | `status` | Map: Unshipped→pending, Shipped→shipped, Canceled→cancelled |
| `purchaseDate` | Not in OrderCreate | Stored in audit log |
| `fulfillmentChannel` | Not in OrderCreate | Checked: must be "MFN" (merchant fulfilled) |
| `buyerInfo.name` | `customer_name` | **PII — redacted in logs** |
| `shippingAddress` | `shipping_address` | **PII — redacted in logs** |
| `orderItems[].sellerSKU` | `sku` | Direct mapping |
| `orderItems[].title` | `product_name` | Direct mapping |
| `orderItems[].quantityOrdered` | `quantity` | Direct mapping |

---

## Amazon Status → Internal Status Mapping

| Amazon Status | Internal Status | Notes |
|--------------|----------------|-------|
| `Unshipped` | `pending` | Needs fulfillment |
| `PartiallyShipped` | `processing` | Partial fulfillment |
| `Shipped` | `shipped` | Already fulfilled |
| `Canceled` | `cancelled` | No action needed |
| `Unfulfillable` | N/A | Cannot fulfill — flag for review |

---

## Validation Rules

After transformation:

1. **SKU must exist** — map to internal inventory
2. **Quantity must be ≥ 1**
3. **Shipping address must be valid** — process through AddressProcessor
4. **Fulfillment channel must be MFN** — FBA orders are not our responsibility
5. **Order must not already exist** — dedup by external reference ID

---

## PII Handling at Boundary

```python
def to_internal_order(self, amazon_order: dict) -> OrderCreate:
    """Transform Amazon order to internal OrderCreate.
    
    PII is included here for fulfillment purposes,
    but will be redacted in all logs and audit records.
    """
    return OrderCreate(
        customer_name=amazon_order["buyer_name"],  # PII
        shipping_address=amazon_order["address"],   # PII
        product_name=amazon_order["product_name"],
        sku=amazon_order["sku"],
        quantity=amazon_order["quantity"],
        status=map_status(amazon_order["order_status"]),
    )
```

The PII enters the system here but is immediately:
1. Stored only in the Order model (for fulfillment)
2. Redacted in all audit/log entries
3. Never exposed via API responses (except to authorized users)
4. Never sent to external services

---

## Key Insight

The transformation is simple because:
- The internal `OrderCreate` schema is already minimal
- Amazon provides more data than we need
- We reject/ignore Amazon fields we don't need
- The fulfillment engine works with `OrderCreate` regardless of source
