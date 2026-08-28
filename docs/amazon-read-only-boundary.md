# Read-Only Boundary Definition

## CHUNK 1U — Official Amazon Sandbox / Developer Environment

---

## CHUNK 1U May Prepare

| Item | Status | Notes |
|------|--------|-------|
| Developer environment documentation | ✅ Done | This document |
| Sandbox configuration design | ✅ Done | Environment variables |
| Provider configuration design | ✅ Done | AmazonOrderProvider stub |
| Authentication configuration design | ✅ Done | LWA OAuth flow |
| Test data strategy | ✅ Done | Sandbox static responses |
| Read-only API design | ✅ Done | searchOrders, getOrder |

---

## CHUNK 1U Must NOT Implement

| Item | Status | Reason |
|------|--------|--------|
| Production Amazon API | ❌ Not yet | Wait for CHUNK 1W |
| Real OAuth flow | ❌ Not yet | Wait for CHUNK 1V |
| Real token exchange | ❌ Not yet | Wait for CHUNK 1V |
| Real SP-API calls | ❌ Not yet | Wait for CHUNK 1V |
| Order modification | ❌ Never | Out of scope |
| Order cancellation | ❌ Never | Out of scope |
| Purchase/payment | ❌ Never | Out of scope |
| Supplier interaction | ❌ Never | Out of scope |
| Automated Seller Central | ❌ Never | Out of scope |
| Browser automation | ❌ Never | Out of scope |

---

## CHUNK 1V Will Implement

| Item | Description |
|------|-------------|
| Real LWA token exchange | Exchange authorization code for tokens |
| Real SP-API calls | Call sandbox endpoints |
| Order retrieval | searchOrders, getOrder |
| Order mapping | Amazon response → internal OrderCreate |
| Provider activation | AmazonOrderProvider becomes active |
| Integration testing | End-to-end with sandbox data |

---

## CHUNK 1V Will NOT Implement

| Item | Description |
|------|-------------|
| Fulfillment submission | Still requires approval gate |
| Order modification | Out of scope |
| Order cancellation | Out of scope |
| PII access | Requires additional approval |
| Production endpoints | Wait for CHUNK 1W |
| Real seller data | Wait for CHUNK 1W |

---

## Boundary Diagram

```
CHUNK 1U (Current)
├── Documentation ✅
├── Environment design ✅
├── Provider stub ✅
├── Safety verification ✅
└── NO real Amazon calls

CHUNK 1V (Future)
├── Real LWA authentication
├── Real SP-API calls (sandbox)
├── Read-only order retrieval
├── Provider activation
├── Integration testing
└── NO fulfillment submission

CHUNK 1W+ (Far Future)
├── Production credentials
├── Production endpoints
├── Full read-only + approval-gated fulfillment
├── Production readiness review
└── Explicit approval required
```
