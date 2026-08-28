# Failure Handling Requirements

## CHUNK 1R — Official API Readiness & Compliance Design

Future behavior for Amazon API failures and edge cases.

---

## Failure Scenarios and Responses

| Failure | Response | Retry? | User Action |
|---------|----------|--------|-------------|
| Amazon API unavailable | Log error, return to caller | Yes (with backoff) | Wait and retry |
| Authentication failure | Log error, raise ProviderAuthenticationError | No | Re-authorize |
| Authorization failure | Log error, raise ProviderAuthenticationError | No | Check permissions |
| Rate limit exceeded | Log warning, wait and retry | Yes (with exponential backoff) | Wait |
| Timeout | Log error, retry once | Yes (single retry) | Wait and retry |
| Malformed response | Log error, raise ProviderValidationError | No | Report issue |
| Missing order | Log error, raise NotFoundError | No | Verify order ID |
| Missing order item | Log warning, skip item | No | Report incomplete data |
| Restricted data (PII blocked) | Log warning, use available data | No | Request PII approval |
| Invalid address | Process through AddressProcessor | N/A | Review if needed |
| Duplicate order | Skip import, log audit event | No | No action needed |
| Already fulfilled order | Skip workflow, log audit event | No | No action needed |
| Amazon status mismatch | Log warning, use latest status | No | Review |
| Provider outage | Log error, return cached data if available | Yes (with backoff) | Wait |
| Partial response | Log warning, process available data | No | Report incomplete |

---

## Retry Strategy

```
Attempt 1: Immediate
    ↓ (failure)
Wait 1 second
    ↓ (failure)
Wait 2 seconds
    ↓ (failure)
Wait 4 seconds
    ↓ (failure)
Wait 8 seconds
    ↓ (failure)
Stop — log error, notify user
```

**Maximum retries: 5**
**Maximum total wait: ~30 seconds**
**Never retry indefinitely**

---

## Duplicate Prevention

No automatic retry loop should create duplicate:

1. **Duplicate Amazon import** — Check external reference ID before import
2. **Duplicate internal order** — Check order existence before creation
3. **Duplicate fulfillment workflow** — Check active workflow before starting
4. **Duplicate supplier submission** — Check confirmation before submitting
5. **Duplicate shipment submission** — Check shipment status before confirming

---

## Error Propagation

```
Amazon API Error
    ↓
Provider Adapter (catches, logs, wraps in ProviderError)
    ↓
Service Layer (catches ProviderError, logs, returns error to caller)
    ↓
API Layer (catches service error, returns HTTP error)
    ↓
Frontend (displays error to user)
```

**Errors never propagate as raw Amazon errors.** They are wrapped in the existing `ProviderError` hierarchy.

---

## Graceful Degradation

If Amazon API is unavailable:
1. Use cached data if available
2. Show user that Amazon is unavailable
3. Continue with mock data if in sandbox mode
4. Never crash the application
