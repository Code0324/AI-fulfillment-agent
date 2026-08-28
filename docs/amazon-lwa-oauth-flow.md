# Amazon LWA OAuth Flow

## CHUNK 1T — Amazon LWA Credentials & Authentication Architecture Review

Based on official Amazon documentation (developer-docs.amazon.com).

**This is documentation only. No real OAuth flow is implemented.**

---

## Authorization Flow Overview

### Public Applications (OAuth 2.0 Authorization Code Grant)

```
Seller/Authorized User
        │
        ▼
1. User visits our application
        │
        ▼
2. Application redirects to Amazon Authorization URL
   https://www.amazon.com/ap/oa
   Parameters:
     - client_id (LWA Client ID)
     - scope (sellingpartnerapi::orders)
     - redirect_uri (our callback URL)
     - state (CSRF protection token)
        │
        ▼
3. Seller logs in to Amazon
   - Enters credentials
   - Reviews requested permissions
        │
        ▼
4. Amazon redirects back to our callback URL
   Parameters:
     - authorization_code (short-lived code)
     - state (must match step 2)
        │
        ▼
5. Backend exchanges code for tokens
   POST https://api.amazon.com/auth/o2/token
   Body:
     - grant_type=authorization_code
     - code (from step 4)
     - client_id
     - client_secret
        │
        ▼
6. Amazon returns tokens
   Response:
     - access_token (expires in 1 hour)
     - refresh_token (long-lived)
     - token_type=bearer
     - expires_in=3600
        │
        ▼
7. Backend stores tokens securely
   - refresh_token → secure storage
   - access_token → in-memory (auto-refresh)
        │
        ▼
8. Application can now call SP-API
```

### Private Applications (Self-Authorization)

```
Developer/Admin
        │
        ▼
1. Developer logs in to Seller Central
        │
        ▼
2. Developer navigates to Apps & Services → Develop Apps
        │
        ▼
3. Developer creates application
   - Gets LWA Client ID
   - Gets LWA Client Secret
        │
        ▼
4. Developer performs self-authorization
   - Clicks "Authorize" button
   - Amazon generates refresh token
        │
        ▼
5. Developer stores credentials
   - Client ID → secure storage
   - Client Secret → secure storage
   - Refresh Token → secure storage
        │
        ▼
6. Application can now call SP-API
```

---

## Token Lifecycle

### Access Token

| Property | Value |
|----------|-------|
| Lifetime | 1 hour (3600 seconds) |
| Format | Starts with `Atza\|` |
| Storage | In-memory only |
| Refresh | Auto-refresh before expiry |
| Exposure | Never sent to frontend |

### Refresh Token

| Property | Value |
|----------|-------|
| Lifetime | Long-lived (valid indefinitely unless revoked) |
| Format | Starts with `Atzr\|` |
| Max size | 2048 bytes |
| Storage | Secure encrypted storage |
| Rotation | Required annually (reauthorization) |
| Revocation | Seller can revoke in Seller Central |

### Token Refresh Flow

```
Current Access Token
        │
        ▼
Access Token expired or about to expire
        │
        ▼
Backend uses Refresh Token
POST https://api.amazon.com/auth/o2/token
Body:
  - grant_type=refresh_token
  - refresh_token
  - client_id
  - client_secret
        │
        ▼
Amazon returns new Access Token
Response:
  - access_token (new, 1 hour expiry)
  - No new refresh token
        │
        ▼
Backend updates in-memory access token
        │
        ▼
Continues with SP-API calls
```

---

## Reauthorization Requirements

| Trigger | Action Required |
|---------|----------------|
| Annual rotation | Seller must re-authorize |
| New roles added | Seller must re-authorize |
| Refresh token revoked | Full re-authorization needed |
| App permissions changed | Seller must re-authorize |

---

## Required Application Credentials

| Credential | Source | Sensitivity |
|-----------|--------|-------------|
| LWA Client ID | Developer Central | HIGH |
| LWA Client Secret | Developer Central | CRITICAL |
| Refresh Token | OAuth flow / self-auth | CRITICAL |
| Access Token | Token exchange | HIGH (temporary) |

---

## Redirect/Callback Considerations

| Requirement | Details |
|-------------|---------|
| Exact URI match | Amazon validates exact redirect URI |
| HTTPS required | Production must use HTTPS |
| No wildcards | Each redirect URI must be explicitly registered |
| Single use | Authorization codes are single-use |
| Short-lived | Codes expire quickly (typically 5 minutes) |

---

## Seller Authorization Considerations

| Consideration | Details |
|--------------|---------|
| Permissions | Seller approves specific API scopes |
| Revocation | Seller can revoke at any time |
| Annual renewal | Reauthorization required annually |
| Multi-seller | Each seller authorizes separately |
| Audit trail | Authorization events are logged by Amazon |
