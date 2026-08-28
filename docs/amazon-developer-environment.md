# Amazon Developer Environment Design

## CHUNK 1U — Official Amazon Sandbox / Developer Environment

---

## Environment Progression

```
┌─────────────────────────────────────────────────────────────────┐
│  LOCAL MOCK (CHUNK 1Q-1T)                                        │
│  MOCK_ONLY=True                                                 │
│  No external network                                            │
│  Synthetic data                                                 │
│  All providers are mock                                         │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  AMAZON SANDBOX (CHUNK 1U)                                       │
│  MOCK_ONLY=True (still)                                         │
│  Sandbox endpoints configured                                   │
│  Test credentials (if available)                                │
│  Static mock responses                                          │
│  Read-only operations only                                      │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  READ-ONLY INTEGRATION (CHUNK 1V)                                │
│  MOCK_ONLY=False (only when ready)                              │
│  Real LWA credentials (sandbox environment)                     │
│  Real SP-API calls to sandbox endpoints                         │
│  Read-only order retrieval                                      │
│  No fulfillment submission                                      │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  PRODUCTION (CHUNK 1W+)                                          │
│  MOCK_ONLY=False                                                │
│  Real LWA credentials (production)                              │
│  Real SP-API calls to production endpoints                      │
│  Full read-only + approval-gated fulfillment                    │
│  Production secrets management                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Local Mock Environment

| Aspect | Configuration |
|--------|---------------|
| MOCK_ONLY | True |
| Network | No external calls |
| Data | Synthetic (AMZ-MOCK-*) |
| Providers | MockOrderProvider, MockSupplierProvider, MockTrackingProvider |
| Amazon provider | Not registered |
| Credentials | None required |
| Testing | All local |

**Status**: ✅ Complete (CHUNK 1Q)

---

## Amazon Sandbox Environment

| Aspect | Configuration |
|--------|---------------|
| MOCK_ONLY | True (still safe) |
| Network | Sandbox endpoints (no production) |
| Data | Static mock responses from Amazon |
| Providers | MockOrderProvider (primary) |
| Amazon provider | Stub only (not active) |
| Credentials | Sandbox LWA credentials (if available) |
| Testing | Sandbox API validation |

**Status**: 🟡 CHUNK 1U (current)

**Key Point**: Even in sandbox mode, MOCK_ONLY remains True until CHUNK 1V when we explicitly enable real API calls.

---

## Read-Only Integration Environment

| Aspect | Configuration |
|--------|---------------|
| MOCK_ONLY | False (explicit opt-in) |
| Network | Real SP-API calls to sandbox endpoints |
| Data | Sandbox mock data |
| Providers | AmazonOrderProvider (active) |
| Credentials | Real LWA credentials (sandbox) |
| Operations | Read-only (searchOrders, getOrder) |
| Fulfillment | Still requires approval gate |
| Testing | Integration testing with sandbox |

**Status**: 🔵 CHUNK 1V (future)

**Key Point**: Read-only only. No fulfillment submission. No order modification.

---

## Production Environment

| Aspect | Configuration |
|--------|---------------|
| MOCK_ONLY | False |
| Network | Real SP-API calls to production endpoints |
| Data | Real seller data |
| Providers | AmazonOrderProvider (active) |
| Credentials | Production LWA credentials (secrets manager) |
| Operations | Read-only + approval-gated fulfillment |
| Fulfillment | Requires human approval |
| Testing | Production readiness review |

**Status**: 🔴 CHUNK 1W+ (far future)

**Key Point**: Production requires explicit approval and full security review.

---

## Environment Separation Rules

| Rule | Description |
|------|-------------|
| No cross-env credentials | Sandbox credentials don't work in production |
| MOCK_ONLY enforcement | `MOCK_ONLY=True` prevents all real API calls |
| Separate LWA apps | Different Amazon apps for sandbox vs production |
| Separate refresh tokens | Different tokens per environment |
| Audit trail | All environments log authentication events |
| Secret isolation | Production secrets in secrets manager only |

---

## Development Workflow

```
1. Develop locally with MOCK_ONLY=True
   ↓
2. Validate sandbox configuration (CHUNK 1U)
   ↓
3. Test with sandbox endpoints (CHUNK 1V)
   ↓
4. Production readiness review (CHUNK 1W)
   ↓
5. Enable production (only with explicit approval)
```
