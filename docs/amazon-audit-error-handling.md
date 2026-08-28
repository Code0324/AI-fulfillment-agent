# Amazon Audit Events & Error Handling

## CHUNK 1T — Amazon LWA Credentials & Authentication Architecture Review

---

## Authentication Audit Events

| Event Type | Category | PII? | Description |
|-----------|----------|------|-------------|
| `AMAZON_CONNECTION_INITIATED` | Auth | No | User started Amazon connection flow |
| `AMAZON_AUTHORIZATION_STARTED` | Auth | No | OAuth flow initiated |
| `AMAZON_AUTHORIZATION_COMPLETED` | Auth | No | OAuth flow completed successfully |
| `AMAZON_AUTHORIZATION_FAILED` | Auth | No | OAuth flow failed |
| `AMAZON_TOKEN_REFRESHED` | Auth | No | Access token refreshed successfully |
| `AMAZON_TOKEN_REFRESH_FAILED` | Auth | No | Token refresh failed (needs reauth) |
| `AMAZON_CONNECTION_REVOKED` | Auth | No | Connection revoked by user |
| `AMAZON_CONNECTION_DISCONNECTED` | Auth | No | Connection disconnected |
| `AMAZON_CREDENTIAL_ACCESSED` | Security | No | Credential accessed (log redacted) |
| `AMAZON_CREDENTIAL_ROTATED` | Security | No | Credential rotated |

### NEVER Log

| Data | Reason |
|------|--------|
| Client Secret | CRITICAL security |
| Refresh Token | CRITICAL security |
| Access Token | HIGH security |
| Authorization Code | HIGH security (ephemeral) |
| Raw credentials | CRITICAL security |

### Always Redact

Apply `redact_pii()` and `redact_secret()` to all audit entries.

---

## Error Handling Matrix

| Error | Response | Retry? | User Action |
|-------|----------|--------|-------------|
| Authorization denied | Log error, mark connection failed | No | Re-authorize |
| Invalid authorization code | Log error, return to OAuth flow | No | Restart connection |
| Expired access token | Auto-refresh using refresh token | Yes (once) | None (auto) |
| Expired refresh token | Log error, mark needs_reauth | No | Re-authorize |
| Invalid credentials | Log error, mark connection failed | No | Check credentials |
| Revoked authorization | Log error, mark disconnected | No | Re-authorize |
| Seller account unavailable | Log error, return error to user | No | Wait and retry |
| Permission denied | Log error, return error to user | No | Check permissions |
| Rate limit exceeded | Wait and retry | Yes (with backoff) | Wait |
| Amazon service unavailable | Log error, return error to user | Yes (with backoff) | Wait and retry |
| Network timeout | Log error, retry once | Yes (single retry) | Wait and retry |
| Malformed Amazon response | Log error, return error to user | No | Report issue |

---

## Error Propagation

```
Amazon SP-API Error
        │
        ▼
AmazonOrderProvider (catches, wraps in ProviderError)
        │
        ▼
Service Layer (catches ProviderError, logs, returns error)
        │
        ▼
API Layer (catches service error, returns HTTP error)
        │
        ▼
Frontend (displays error to user)
```

**Errors never propagate as raw Amazon errors.** They are wrapped in the existing `ProviderError` hierarchy.

---

## Token Refresh Safety

### Refresh Mechanism

```python
# Conceptual future implementation

class TokenRefreshManager:
    """Manages safe token refresh for Amazon LWA."""
    
    def __init__(self):
        self._locks: dict[str, threading.Lock] = {}  # per-tenant locks
    
    def get_access_token(self, tenant_id: str) -> str:
        """Get a valid access token, refreshing if needed."""
        lock = self._get_lock(tenant_id)
        with lock:
            token_store = self._get_token_store(tenant_id)
            
            # Check if token is still valid (with 5-min buffer)
            if token_store.is_valid(expires_within_seconds=300):
                return token_store.access_token
            
            # Refresh needed
            try:
                new_token = self._refresh_token(tenant_id)
                token_store.update(new_token)
                return new_token
            except RefreshFailedError:
                # Mark tenant as needing reauthorization
                self._mark_needs_reauth(tenant_id)
                raise ProviderAuthenticationError("amazon_order_provider")
    
    def _refresh_token(self, tenant_id: str) -> str:
        """Exchange refresh token for new access token."""
        refresh_token = self._get_refresh_token(tenant_id)
        
        # POST https://api.amazon.com/auth/o2/token
        # grant_type=refresh_token
        # refresh_token=...
        # client_id=...
        # client_secret=...
        
        # On success: return new access_token
        # On failure: raise RefreshFailedError
        ...
```

### Safety Properties

| Property | Implementation |
|----------|---------------|
| No token in logs | `redact_secret()` applied to all log entries |
| No token in errors | Tokens stripped from exception messages |
| No token to frontend | Backend only, never exposed via API |
| Concurrent refresh safe | Per-tenant lock prevents races |
| Revoked token handling | Stop API calls, require reauthorization |
| Auto-refresh | 5-minute buffer before expiry |

---

## Failure Isolation

| Failure | Impact | Recovery |
|---------|--------|----------|
| Token refresh fails | One tenant affected | Reauthorization required |
| Amazon API fails | One tenant affected | Retry or wait |
| Credential store fails | All tenants affected | System-level recovery |
| Rate limit hit | One tenant affected | Wait and retry |
| Network timeout | One tenant affected | Retry once |
