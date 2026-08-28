# PII and Security Boundaries

## CHUNK 1R — Official API Readiness & Compliance Design

---

## Amazon Customer Information Received

When using the Orders API, the following PII may be received:

| Data | Risk Level | Received via |
|------|-----------|--------------|
| Buyer Name | HIGH | `getOrder` / `searchOrders` |
| Buyer Email | HIGH | `getOrderBuyerInfo` (v0 only) |
| Shipping Address | HIGH | `getOrder` / `searchOrders` |
| Phone Number | HIGH | Shipping address |
| Order ID | LOW | `getOrder` / `searchOrders` |
| SKU | LOW | Order items |

---

## What Is Actually Needed

For our fulfillment workflow, we need:

1. **Customer Name** — for address processing and fulfillment
2. **Shipping Address** — for delivery destination
3. **Phone** — only if needed for delivery (may be optional)
4. **SKU** — for inventory mapping
5. **Quantity** — for inventory reservation
6. **Order Status** — for workflow decisions

We do **NOT** need:
- Buyer email
- Payment information
- Order analytics
- Marketplace-specific metadata

---

## What Should Never Be Logged

| Data | Logging Rule |
|------|-------------|
| Buyer Name | REDACT in all logs |
| Buyer Email | NEVER log |
| Full Shipping Address | REDACT — show only city/state |
| Phone Number | REDACT in all logs |
| Amazon Order ID | Safe to log (not PII) |
| SKU | Safe to log |
| API Tokens/Credentials | NEVER log |

---

## What Should Be Redacted

Apply `redact_pii()` from `app.core.security` to all:

1. Audit log entries
2. Error messages
3. Debug output
4. API responses (except to authorized internal users)

Current `redact_pii()` handles:
- Phone numbers (US format)
- ZIP/postal codes
- Email addresses

**Future enhancement needed**: Add name redaction for full PII protection.

---

## What Should Not Be Persisted

| Data | Persistence Rule |
|------|-----------------|
| Buyer Email | Do not store |
| Amazon API Tokens | Store in secure secrets manager only |
| Full Buyer Profile | Do not store |
| Order Analytics | Do not store |
| Buyer Phone | Store only if needed for delivery |

---

## Existing PII Protection

The project already has:

1. **`redact_pii()`** in `app/core/security.py`
   - Redacts phone numbers, ZIP codes, emails
   - Used in audit logs and error messages

2. **`safe_log_address()`** in `app/core/security.py`
   - Shows only city/state, redacts details

3. **Audit events** never contain full PII
   - Use redacted details

---

## Credential Handling Requirements (Future)

For a future Amazon integration:

| Requirement | Design |
|-------------|--------|
| LWA Client ID | Store in environment variable |
| LWA Client Secret | Store in secrets manager (never in code) |
| Refresh Token | Store in secrets manager |
| Access Tokens | In-memory only, auto-refresh |
| Token Rotation | Mandatory every 180 days |
| Credential Access | Only by provider adapter, never by workflow |
| Credential Logging | NEVER log credentials |
| Credential in Git | NEVER commit credentials |

---

## Secret Storage Requirements

```
.env (development only)
├── AMAZON_LWA_CLIENT_ID
├── AMAZON_LWA_CLIENT_SECRET
├── AMAZON_REFRESH_TOKEN
└── AMAZON_MARKETPLACE_ID

Production
└── Secrets Manager (AWS, HashiCorp Vault, etc.)
    ├── amazon-lwa-client-id
    ├── amazon-lwa-client-secret
    └── amazon-refresh-token
```

---

## Token Lifecycle Requirements

```
OAuth Authorization Flow
        ↓
Refresh Token (long-lived, rotate every 180 days)
        ↓
Access Token (short-lived, ~1 hour)
        ↓
API Calls
        ↓
Token Expiry → Auto-refresh using Refresh Token
        ↓
Refresh Token Expiry → Re-authorize with seller
```

---

## Audit Requirements

All Amazon interactions must be audited:

1. **Authentication events** — token refresh, authorization
2. **API calls** — request/response (without PII)
3. **Data transformations** — Amazon → Internal
4. **Errors** — API failures, rate limits
5. **PII access** — when buyer info is accessed

Audit records must:
- Never contain PII
- Include timestamps
- Include operation type
- Include success/failure status
- Be tamper-evident (append-only)
