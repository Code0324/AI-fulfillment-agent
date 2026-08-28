# Amazon Credential Types

## CHUNK 1T — Amazon LWA Credentials & Authentication Architecture Review

---

## Credential Categories

### 1. Application Credentials (LWA)

| Credential | Purpose | Sensitivity | Storage | Lifetime | Rotation |
|-----------|---------|-------------|---------|----------|----------|
| LWA Client ID | Identifies our application to Amazon | HIGH | Secrets Manager | Permanent (unless rotated) | As needed |
| LWA Client Secret | Proves application identity to Amazon | CRITICAL | Secrets Manager | Permanent (unless rotated) | As needed |

**Logging**: NEVER log these values
**Access**: Only by authentication layer, never by frontend or fulfillment engine

### 2. Authorization Credentials

| Credential | Purpose | Sensitivity | Storage | Lifetime | Rotation |
|-----------|---------|-------------|---------|----------|----------|
| Refresh Token | Obtains new access tokens | CRITICAL | Secrets Manager / encrypted DB | Long-lived (revocable) | Annual reauthorization |
| Authorization Code | Temporary code for token exchange | HIGH | Ephemeral (in-memory only) | Single-use, expires in ~5 min | N/A (one-time) |

**Logging**: NEVER log these values
**Access**: Only by authentication layer

### 3. API Tokens (Runtime)

| Credential | Purpose | Sensitivity | Storage | Lifetime | Rotation |
|-----------|---------|-------------|---------|----------|----------|
| Access Token | Authenticates SP-API requests | HIGH | In-memory only | 1 hour | Auto-refresh |

**Logging**: NEVER log this value
**Access**: Only by AmazonOrderProvider, never exposed to frontend

### 4. Seller/Account Identifiers

| Credential | Purpose | Sensitivity | Storage | Lifetime | Rotation |
|-----------|---------|-------------|---------|----------|----------|
| Amazon Marketplace ID | Identifies marketplace | LOW | Config / DB | Permanent | N/A |
| Seller ID | Identifies seller account | LOW | DB (per tenant) | Permanent | N/A |
| AWS Access Key | For SP-API signature (if using AWS SDK) | CRITICAL | Secrets Manager | Rotatable | As needed |
| AWS Secret Key | For SP-API signature (if using AWS SDK) | CRITICAL | Secrets Manager | Rotatable | As needed |

**Logging**: Safe to log Marketplace ID. NEVER log AWS keys.
**Access**: Marketplace ID accessible to frontend. AWS keys only by auth layer.

---

## Storage Location Rules

| Credential Type | Development | Production |
|----------------|-------------|------------|
| LWA Client ID | Environment variable | Secrets Manager |
| LWA Client Secret | Environment variable | Secrets Manager |
| Refresh Token | Environment variable | Secrets Manager (encrypted) |
| Access Token | In-memory | In-memory |
| AWS Keys | Environment variable | Secrets Manager |
| Marketplace ID | Config / env var | Config / env var |

---

## Access Restrictions

| Who | Can Access | Cannot Access |
|-----|-----------|---------------|
| Frontend | Connection status only | Any credentials/tokens |
| Fulfillment Engine | None directly | Any credentials/tokens |
| AmazonOrderProvider | Access token (injected) | Refresh token, client secret |
| Auth Layer | All credentials | N/A (owns them) |
| Audit System | Redacted values only | Raw credentials |
| Test Fixtures | Mock credentials only | Real credentials |

---

## Logging Restrictions

| Credential | Log as | Never Log |
|-----------|--------|-----------|
| Client ID | `[LWA_CLIENT_ID]` | Actual value |
| Client Secret | `***` (redacted) | Actual value |
| Refresh Token | `***` (redacted) | Actual value |
| Access Token | `***` (redacted) | Actual value |
| Authorization Code | Never logged | Actual value |
| AWS Keys | `***` (redacted) | Actual value |
