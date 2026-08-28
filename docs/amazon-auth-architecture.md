# Amazon LWA Authentication Architecture

## CHUNK 1T — Amazon LWA Credentials & Authentication Architecture Review

---

## Authentication Boundary Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     EXTERNAL (Amazon)                           │
│                                                                 │
│   Amazon LWA OAuth 2.0                                          │
│   Authorization Code Grant                                      │
│   Token Exchange                                                │
│                                                                 │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                    [ AUTHENTICATION BOUNDARY ]
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                  AUTHENTICATION LAYER                           │
│                                                                 │
│   AmazonAuthManager                                             │
│     ├── OAuth flow (authorization URL, callback)                │
│     ├── Token exchange (authorization code → tokens)            │
│     ├── Token refresh (refresh token → new access token)        │
│     ├── Token storage (secure, encrypted)                       │
│     └── Credential management                                   │
│                                                                 │
│   Credentials/Tokens stay INSIDE this layer:                    │
│     - LWA Client ID                                             │
│     - LWA Client Secret                                         │
│     - Refresh Token                                             │
│     - Access Token (short-lived)                                │
│                                                                 │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                    [ TOKEN BOUNDARY ]
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                  AMAZON PROVIDER ADAPTER                        │
│                                                                 │
│   AmazonOrderProvider                                           │
│     ├── Uses access token (injected by auth layer)              │
│     ├── Makes SP-API calls                                      │
│     ├── Transforms Amazon responses → Internal OrderCreate      │
│     └── Redacts PII at boundary                                 │
│                                                                 │
│   NO credentials stored here — only used                        │
│                                                                 │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                    [ PROVIDER BOUNDARY ]
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                 EXISTING INTERNAL SYSTEM                        │
│                                                                 │
│   OrderService                                                  │
│   InventoryService                                              │
│   AddressProcessingService                                       │
│   FulfillmentWorkflowEngine                                      │
│   ApprovalGate                                                  │
│                                                                 │
│   NO Amazon-specific code exists here.                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Key Principle

**Authentication does NOT imply permission to fulfill.**

Even after Amazon authentication is established:
1. Orders are read-only
2. Fulfillment requires approval gate
3. External submissions require human approval
4. No auto-fulfillment without explicit user action

---

## Current Security Architecture

### Existing Utilities

| Utility | Location | Purpose |
|---------|----------|---------|
| `redact_pii()` | `app.core.security` | Redacts phone, ZIP, email from text |
| `redact_secret()` | `app.core.security` | Shows only last N chars of secret |
| `safe_log_address()` | `app.core.security` | Redacts address details for logs |
| `MOCK_ONLY` | `app.services.providers.base` | Global flag preventing production usage |
| `ensure_mock_mode()` | `app.services.providers.base` | Raises if MOCK_ONLY is False |

### Existing Configuration

| Setting | Source | Default |
|---------|--------|---------|
| `APP_ENV` | env var | `development` |
| `BACKEND_HOST` | env var | `0.0.0.0` |
| `BACKEND_PORT` | env var | `8000` |
| `FRONTEND_PORT` | env var | `3000` |
| `CORS_ORIGINS` | computed | localhost only |

### What Already Works

1. ✅ Structured logging (respects `redact_pii()`)
2. ✅ PII redaction in audit logs
3. ✅ Address redaction in logs
4. ✅ Secret redaction utility
5. ✅ MOCK_ONLY safety flag
6. ✅ Error handling (no secrets in error messages)
7. ✅ Provider error hierarchy

### What Needs Addition (Future)

1. ❌ Secure credential storage (env vars / secrets manager)
2. ❌ Token lifecycle management
3. ❌ Token encryption at rest
4. ❌ Multi-tenant credential isolation
5. ❌ OAuth callback endpoint
6. ❌ CSRF/state parameter validation
