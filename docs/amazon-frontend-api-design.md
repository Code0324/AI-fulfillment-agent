# Frontend Security Boundary & API Design

## CHUNK 1T — Amazon LWA Credentials & Authentication Architecture Review

---

## Frontend Security Boundary

### Frontend MAY Receive

| Data | Purpose | Example |
|------|---------|---------|
| Connection status | Show connection state | `connected`, `disconnected`, `needs_reauth` |
| Last sync time | Show when data was last fetched | `2026-01-15T10:00:00Z` |
| Sync status | Show import state | `syncing`, `idle`, `error` |
| Non-sensitive errors | Show user-friendly errors | "Connection expired, please re-authorize" |
| Marketplace info | Show which marketplace | `Amazon.com (US)` |

### Frontend MUST NOT Receive

| Data | Reason |
|------|--------|
| Access Token | Security — never expose |
| Refresh Token | CRITICAL — never expose |
| Client Secret | CRITICAL — never expose |
| Client ID | Security — not needed by frontend |
| Authorization Code | Ephemeral — never stored |
| Raw credentials | Security — never expose |

---

## API Endpoint Design (Future — Documentation Only)

### Connection Management

```
GET    /api/v1/amazon/connection/status
       → Returns connection status for current tenant
       → Response: { status, marketplace, last_sync, sync_status }

POST   /api/v1/amazon/connection/start
       → Initiates OAuth flow
       → Returns: { authorization_url, state }
       → User redirected to Amazon

GET    /api/v1/amazon/connection/callback
       → Handles OAuth callback from Amazon
       → Validates state parameter
       → Exchanges code for tokens
       → Returns: { status: "connected" }

POST   /api/v1/amazon/connection/disconnect
       → Revokes connection
       → Deletes stored tokens
       → Returns: { status: "disconnected" }

POST   /api/v1/amazon/connection/reauthorize
       → Re-initiates OAuth for existing connection
       → Returns: { authorization_url, state }
```

### Order Operations

```
POST   /api/v1/amazon/orders/import
       → Imports orders from Amazon
       → Returns: { imported, skipped_duplicates }

GET    /api/v1/amazon/orders/status
       → Returns import/sync status
       → Returns: { last_import, total_imported, errors }
```

### Security

All endpoints require:
1. Authentication (user must be logged in)
2. Authorization (user must have appropriate role)
3. Tenant context (scoped to current tenant)

---

## OAuth Callback Security

### State Parameter

```
1. Generate random state token
   state = generate_csrf_token()

2. Store state with session/user binding
   session.oauth_state = state
   session.oauth_state_expires = now + 5 minutes

3. Include state in authorization URL
   /ap/oa?...&state={state}

4. On callback, validate state
   if callback.state != session.oauth_state:
       reject("CSRF detected")
   if now > session.oauth_state_expires:
       reject("State expired")
```

### CSRF Protection

| Requirement | Implementation |
|-------------|---------------|
| State parameter | Random, cryptographically secure |
| State binding | Bound to user session |
| State expiry | 5 minutes max lifetime |
| State single-use | Consumed on callback |
| Exact redirect URI | Amazon validates exact match |

### Redirect URI Validation

```
Allowed redirect URIs:
├── https://app.example.com/api/v1/amazon/connection/callback (production)
├── http://localhost:3000/api/v1/amazon/connection/callback (development)
└── https://sandbox.app.example.com/api/v1/amazon/connection/callback (sandbox)

Rules:
- Exact match required
- HTTPS required in production
- No wildcards
- Registered with Amazon developer console
```

### Replay Prevention

| Mechanism | Description |
|-----------|-------------|
| Single-use codes | Authorization codes are single-use |
| Short-lived codes | Codes expire in ~5 minutes |
| State validation | Prevents CSRF replay |
| Nonce | Optional additional replay protection |

---

## Environment Separation

### Development

```
APP_ENV=development
MOCK_ONLY=True
AMAZON_ENV=sandbox
AMAZON_LWA_CLIENT_ID=amzn1.application-oa2-client-dev.xxxxx
AMAZON_LWA_CLIENT_SECRET=xxxxx (sandbox only)
AMAZON_REFRESH_TOKEN=Atzr|xxxxx (sandbox only)
```

### Testing

```
APP_ENV=testing
MOCK_ONLY=True
AMAZON_ENV=sandbox
# Same as development, used for automated tests
```

### Sandbox (Amazon Sandbox)

```
APP_ENV=sandbox
MOCK_ONLY=False  # Only when ready for 1U
AMAZON_ENV=sandbox
AMAZON_LWA_CLIENT_ID=amzn1.application-oa2-client-sandbox.xxxxx
AMAZON_LWA_CLIENT_SECRET=xxxxx
AMAZON_REFRESH_TOKEN=Atzr|xxxxx
```

### Production

```
APP_ENV=production
MOCK_ONLY=False  # Only when ready for 1W+
AMAZON_ENV=production
# All credentials from Secrets Manager
# No credentials in environment variables
```

### Environment Isolation Rules

| Rule | Description |
|------|-------------|
| No cross-env credentials | Sandbox tokens don't work in production |
| MOCK_ONLY enforcement | `MOCK_ONLY=True` prevents all Amazon calls |
| Separate developer apps | Different LWA apps for sandbox vs production |
| Separate refresh tokens | Different tokens per environment |
| Audit trail | All environments log authentication events |
