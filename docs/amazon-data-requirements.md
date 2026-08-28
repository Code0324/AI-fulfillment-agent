# Amazon Data Requirements Matrix

## CHUNK 1R — Official API Readiness & Compliance Design

Minimum Amazon information potentially required for a future official integration.
Follows data minimization principle — only fields justified by the workflow.

---

## Order Data Requirements

| Field | Classification | Justification |
|-------|---------------|---------------|
| Amazon Order ID | **REQUIRED** | Unique order identifier for import and dedup |
| Order Status | **REQUIRED** | Determines whether order needs fulfillment |
| Order Purchase Date | **REQUIRED** | Order creation timestamp |
| Order Last Update Date | **OPTIONAL** | Audit trail |
| Order Total | **NOT REQUIRED** | Not needed for fulfillment logic |
| Order Currency | **NOT REQUIRED** | Not needed for fulfillment logic |
| Marketplace ID | **OPTIONAL** | May be needed for multi-marketplace |
| Sales Channel | **OPTIONAL** | May be needed for marketplace identification |
| Fulfillment Channel | **REQUIRED** | Determines if FBA or FBM (we handle FBM) |
| Payment Method | **NOT REQUIRED** | Payment not in scope |
| Buyer Email | **SENSITIVE / PII** | Must be redacted; not needed for fulfillment |
| Buyer Name | **SENSITIVE / PII** | May be needed for address; must be redacted in logs |
| Amazon Buyer Info | **NOT REQUIRED** | Not needed |

## Order Item Data Requirements

| Field | Classification | Justification |
|-------|---------------|---------------|
| Order Item ID | **REQUIRED** | Unique item identifier |
| ASIN | **OPTIONAL** | Amazon Standard Identification Number |
| Seller SKU | **REQUIRED** | Maps to our inventory SKU |
| Product Name | **REQUIRED** | Item description |
| Quantity Ordered | **REQUIRED** | Determines inventory reservation |
| Quantity Shipped | **OPTIONAL** | Already shipped items |
| Item Price | **NOT REQUIRED** | Payment not in scope |
| Item Tax | **NOT REQUIRED** | Tax not in scope |
| Promotion Discount | **NOT REQUIRED** | Not needed |
| Item Weight | **NOT REQUIRED** | Not needed for current workflow |
| Is Gift | **NOT REQUIRED** | Not needed |
| Gift Message | **NOT REQUIRED** | Not needed |
| Amazon Order Item ID | **REQUIRED** | For dedup and tracking |

## Shipping Address Requirements

| Field | Classification | Justification |
|-------|---------------|---------------|
| Name | **REQUIRED** | Customer name for fulfillment |
| Address Line 1 | **REQUIRED** | Shipping destination |
| Address Line 2 | **OPTIONAL** | Apt/Suite/Unit |
| City | **REQUIRED** | Shipping destination |
| State/Region | **REQUIRED** | Shipping destination |
| Postal Code | **REQUIRED** | Shipping destination |
| Country Code | **REQUIRED** | Shipping destination |
| Phone | **SENSITIVE / PII** | May be needed for delivery; must be redacted in logs |

## Fulfillment/Tracking Requirements

| Field | Classification | Justification |
|-------|---------------|---------------|
| Fulfillment Status | **REQUIRED** | Determines order state |
| Tracking Number | **OPTIONAL** | For status updates |
| Carrier Code | **OPTIONAL** | For tracking |
| Ship Date | **OPTIONAL** | For audit |
| Delivery Date | **NOT REQUIRED** | Not in our scope |

---

## Data Minimization Principle

The system should only request and store:

1. Fields **directly required** by the fulfillment workflow
2. Fields **necessary for deduplication** (Amazon Order ID, Order Item ID)
3. Fields **necessary for audit** (timestamps)

Fields should NOT be stored if:
- They are not used by any workflow step
- They contain PII that is not needed
- They are Amazon-specific metadata not relevant to fulfillment

---

## PII Fields Requiring Protection

| Field | Risk Level | Protection |
|-------|-----------|------------|
| Buyer Name | HIGH | Redact in logs, minimize storage |
| Buyer Email | HIGH | Do not store; redact in logs |
| Shipping Address | HIGH | Store only for fulfillment; redact in logs |
| Phone | HIGH | Store only if needed for delivery; redact in logs |
| Amazon Order ID | LOW | Safe to log (not PII) |
| SKU | LOW | Safe to log |

---

## Future Implementation Note

When implementing the Amazon provider adapter:
1. Only request API scopes needed for the REQUIRED fields
2. Do not store OPTIONAL fields unless a specific workflow need is identified
3. Never store SENSITIVE fields without justification
4. Apply `redact_pii()` to all audit log entries
5. Use field-level access control where possible
