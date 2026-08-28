# Amazon Secret & Token Storage Design

## CHUNK 1T — Amazon LWA Credentials & Authentication Architecture Review

---

## Secret Storage Architecture

### Development Environment

```
.env (gitignored)
├── AMAZON_LWA_CLIENT_ID=amzn1.application-oa2-client.xxxxx
├── AMAZON_LWA_CLIENT_SECRET=xxxxx
├── AMAZON_REFRESH_TOKEN=Atzr|xxxxx
├── AMAZON_MARKETPLACE_ID=ATVPDKIKX0DER
└── AMAZON_APP_TYPE=private
```

**Rules**:
- `.env` is in `.gitignore` — never committed
- `.env.example` contains placeholder values only
- No real credentials in version control
- Development credentials are for sandbox only

### Production Environment

```
Production Application
        │
        ▼
Secrets Manager (AWS Secrets Manager / HashiCorp Vault)
├── amazon-lwa-client-id
├── amazon-lwa-client-secret
├── amazon-refresh-token-{tenant_id}
└── amazon-marketplace-id
```

**Rules**:
- Secrets stored in managed secret store
- Encryption at rest (AES-256)
- Access via IAM roles, not hardcoded keys
- Audit logging on secret access
- Automatic rotation where supported

---

## Token Storage Design

### Access Token (Short-lived)

```
┌─────────────────────────────────────────┐
│           In-Memory Token Store          │
│                                          │
│  tenant_id → {                           │
│    access_token: "Atza|xxxxx",          │
│    expires_at: 2026-01-15T11:00:00Z,   │
│    refreshed_at: 2026-01-15T10:00:00Z  │
│  }                                       │
│                                          │
└─────────────────────────────────────────┘
```

**Properties**:
- Stored in application memory only
- Never persisted to disk
- Never logged
- Auto-refreshed 5 minutes before expiry
- Per-tenant isolation (different tokens for different sellers)

### Refresh Token (Long-lived)

```
┌─────────────────────────────────────────┐
│        Secure Token Store                │
│                                          │
│  Options (choose one):                   │
│                                          │
│  A. Encrypted database column            │
│     - AES-256 encryption at rest         │
│     - Decrypted only when needed         │
│     - Access controlled by tenant_id     │
│                                          │
│  B. Secrets Manager                      │
│     - Full encryption managed            │
│     - Automatic rotation support         │
│     - Audit logging built-in             │
│                                          │
│  C. Encrypted file (dev only)            │
│     - Per-environment file               │
│     - Strong file permissions            │
│     - Gitignored                         │
│                                          │
└─────────────────────────────────────────┘
```

---

## Encryption Requirements

| Data | At Rest | In Transit | Access Control |
|------|---------|-----------|----------------|
| Access Token | In-memory (N/A) | HTTPS | Tenant-scoped |
| Refresh Token | AES-256 encrypted | HTTPS | Tenant-scoped + IAM |
| Client Secret | AES-256 encrypted | HTTPS | Application-scope |
| Authorization Code | Never stored | HTTPS | Ephemeral |

---

## Token Refresh Safety

### Concurrent Refresh Prevention

```
Request 1: Refresh token → acquiring lock
Request 2: Refresh token → waiting for lock
Request 1: Token refreshed → releasing lock
Request 2: Token refreshed → using cached token
```

**Mechanism**: Per-tenant lock on refresh operations.

### Revoked Token Handling

```
Refresh Token Revoked
        │
        ▼
Token Refresh Fails
        │
        ▼
Mark tenant as "needs reauthorization"
        │
        ▼
Stop all Amazon API calls for this tenant
        │
        ▼
Notify administrator
        │
        ▼
Require seller reauthorization
```

---

## Multi-Tenant Token Isolation

```
Tenant A
├── LWA Client ID (shared or per-tenant)
├── Refresh Token A (encrypted, tenant-scoped)
├── Access Token A (in-memory, tenant-scoped)
└── Orders A (isolated)

Tenant B
├── LWA Client ID (shared or per-tenant)
├── Refresh Token B (encrypted, tenant-scoped)
├── Access Token B (in-memory, tenant-scoped)
└── Orders B (isolated)
```

**Rules**:
- Tenant A's tokens cannot access Tenant B's data
- Each tenant has isolated token storage
- Token refresh is tenant-scoped
- Audit logs are tenant-scoped

---

## Development vs Production

| Aspect | Development | Production |
|--------|------------|------------|
| Token storage | Env vars | Secrets Manager |
| Token encryption | N/A (env vars) | AES-256 |
| Token refresh | Manual | Automatic |
| Audit logging | Console | Structured logs |
| Access control | None (dev) | IAM roles |
| Multi-tenant | Single tenant | Full isolation |
