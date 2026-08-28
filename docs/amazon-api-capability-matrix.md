# Amazon SP-API Capability Matrix

## CHUNK 1R — Official API Readiness & Compliance Design

Based on official Amazon Selling Partner API documentation (developer-docs.amazon.com).

**Current version: Orders API v2026-01-01** (v0 is deprecated)

---

## Official API Operations Identified

### Orders API v2026-01-01 (Current)

| Operation | Method | Description | PII Involved |
|-----------|--------|-------------|--------------|
| `searchOrders` | GET | Search orders by criteria | Yes (address, buyer) |
| `getOrder` | GET | Get single order details | Yes (address, buyer) |

### Orders API v0 (Deprecated — Do Not Use)

| Operation | Method | Description | Status |
|-----------|--------|-------------|--------|
| `getOrders` | GET | List orders | **DEPRECATED** |
| `getOrder` | GET | Get order | **DEPRECATED** |
| `getOrderAddress` | GET | Get order address | **DEPRECATED** |
| `getOrderBuyerInfo` | GET | Get buyer info | **DEPRECATED** |
| `getOrderItems` | GET | Get order items | **DEPRECATED** |
| `getOrderItemsBuyerInfo` | GET | Get item buyer info | **DEPRECATED** |
| `confirmShipment` | POST | Confirm shipment | **DEPRECATED** |
| `getOrderRegulatedInfo` | GET | Get regulated info | **DEPRECATED** |
| `updateShipmentStatus` | POST | Update shipment | **DEPRECATED** |
| `updateVerificationStatus` | POST | Update verification | **DEPRECATED** |

**IMPORTANT: The v0 API is deprecated. All new development must use v2026-01-01.**

---

## Capability Matrix for Our Workflow

| Capability | Official API | Read/Write | Required Permission | PII? | Needed by Workflow? | Future Phase |
|------------|-------------|-----------|---------------------|------|--------------------|--------------| 
| Order Search/Retrieval | `searchOrders` | READ | Inventory and Order Tracking | Yes | **YES** | 1V |
| Order Item Retrieval | `getOrder` (includes items) | READ | Inventory and Order Tracking | Yes | **YES** | 1V |
| Order Status | `getOrder` (includes status) | READ | Inventory and Order Tracking | No | **YES** | 1V |
| Shipping Address | `getOrder` (includes address) | READ | Inventory and Order Tracking | **YES — PII** | **YES** | 1V |
| Buyer Information | `getOrder` (includes buyer) | READ | Inventory and Order Tracking | **YES — PII** | **MINIMAL** | 1V |
| Fulfillment Status | `getOrder` (includes fulfillment) | READ | Inventory and Order Tracking | No | **YES** | 1V |
| Shipment/Tracking | `confirmShipment` | WRITE | Inventory and Order Tracking | No | **REQUIRES REVIEW** | 1W+ |
| Order Modification | N/A | — | — | — | **NOT REQUIRED** | N/A |
| Cancellation | N/A | — | — | — | **NOT REQUIRED** | N/A |
| Purchase/Order Creation | N/A | — | — | — | **NOT REQUIRED** | N/A |
| Supplier Interaction | N/A | — | — | — | **NOT IN SCOPE** | N/A |

---

## Required Permissions

For our **read-only** use case, the minimum required role is:

```
Inventory and Order Tracking
```

This single role covers:
- `searchOrders` (v2026-01-01)
- `getOrder` (v2026-01-01)

**NOTE:** If buyer PII access is needed (name, email), additional roles may be required:
- `Buyer Communication`
- `Direct to Consumer Shipping (Restricted)` — **requires additional Amazon approval**

---

## Authentication Requirements

| Requirement | Details |
|-------------|---------|
| Authentication Method | Login with Amazon (LWA) OAuth 2.0 |
| Developer Account | Required — register at developer.amazonservices.com |
| Selling Account | Professional selling account required |
| LWA Credentials | Client ID + Client Secret (rotate every 180 days) |
| Access Tokens | Short-lived tokens (typically 1 hour expiry) |
| Refresh Tokens | Long-lived tokens (obtained via OAuth authorization flow) |
| Token Storage | Must be stored securely (env vars, secrets manager) |
| Token Rotation | Mandatory rotation every 180 days |

---

## Rate Limit Considerations

| Operation | Rate Limit | Our Usage |
|-----------|-----------|-----------|
| `searchOrders` | 0.0167 requests/second (1 per minute) | Low — batch import |
| `getOrder` | 0.0167 requests/second (1 per minute) | Low — on-demand |

**NOTE:** Rate limits are per selling partner. For batch operations, we must implement backoff and retry with jitter.

---

## Application/Developer Requirements

1. **Developer Registration**: Must register at `developer.amazonservices.com`
2. **Solution Provider Portal**: Must have a Solution Provider Portal account
3. **Developer Profile**: Must be approved by Amazon
4. **App Authorization**: Each seller must authorize the app via OAuth
5. **LWA Credential Rotation**: Must rotate credentials every 180 days
6. **Sandbox Access**: Amazon provides a sandbox environment for testing

---

## Additional Amazon Approval Required

The following operations require **separate Amazon approval**:

| Operation | Approval Required | Notes |
|-----------|------------------|-------|
| PII Access (Buyer Info) | **YES** | Requires "Restricted" role approval |
| `confirmShipment` | **YES** | Requires "Direct to Consumer Shipping (Restricted)" |
| `updateShipmentStatus` | **YES** | Requires "Restricted" role approval |
| Order Modification | **OUT OF SCOPE** | Not needed |

**For our initial read-only integration, no additional approval is needed beyond the developer registration and the "Inventory and Order Tracking" role.**

---

## Key Findings

1. **v0 API is deprecated** — must use v2026-01-01
2. **v2026-01-01 is simplified** — only `searchOrders` and `getOrder` operations
3. **Read-only is achievable** with minimal permissions
4. **PII access requires additional approval** — should be avoided initially
5. **Rate limits are strict** — must implement proper backoff
6. **Credential rotation is mandatory** — 180-day cycle
7. **Sandbox is available** — for testing without real seller data
