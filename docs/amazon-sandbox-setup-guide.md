# Amazon Sandbox Setup Guide

## CHUNK 1U — Official Amazon Sandbox / Developer Environment

**This is a manual guide. Do not automate credential creation.**

---

## Prerequisites

Before starting, you need:

1. **Amazon Seller Central account** (Professional selling account)
2. **Email address** for developer registration
3. **Business information** for developer profile

---

## Step 1: Register as Amazon Developer

1. Go to `https://developer.amazonservices.com`
2. Click "Register as a Developer"
3. Choose account type:
   - **Professional Selling Account** — if you sell on Amazon
   - **Solution Provider Portal** — if you build for sellers
4. Complete registration form
5. Verify email address
6. Wait for Amazon approval (may take 1-3 business days)

---

## Step 2: Create SP-API Application

1. Log in to `https://developer.amazonservices.com`
2. Navigate to "Developer Central" → "Apps & Services" → "Develop Apps"
3. Click "Create New Application"
4. Fill in application details:
   - Application Name: `Amazon AI Fulfillment Agent`
   - Application Description: `AI-powered order fulfillment workspace`
   - Application Type: `Private` (for single organization)
5. Submit application

---

## Step 3: Configure LWA Credentials

1. In your application settings, find "LWA Credentials"
2. Click "View" to see:
   - **LWA Client ID** (public identifier)
   - **LWA Client Secret** (keep secret!)
3. Save these securely (see Step 7)

---

## Step 4: Configure OAuth

1. In application settings, find "OAuth Login"
2. Set redirect URIs:
   - Production: `https://your-domain.com/api/v1/amazon/callback`
   - Development: `http://localhost:8000/api/v1/amazon/callback`
3. Save changes

---

## Step 5: Request Required Roles

1. In application settings, find "Roles"
2. Request these roles:
   - **Inventory and Order Tracking** (required for order access)
3. Submit for review
4. Wait for Amazon approval

**Note**: For PII access (buyer info), additional roles may be required:
- `Direct to Consumer Shipping (Restricted)` — requires separate approval

---

## Step 6: Authorize Application

### For Private Applications (Self-Authorization)

1. Log in to Seller Central
2. Go to "Apps & Services" → "Develop Apps"
3. Find your application
4. Click "Authorize"
5. Select the roles you requested
6. Click "Confirm"
7. Save the generated **Refresh Token** securely

### For Public Applications (Seller Authorization)

1. Seller visits your application
2. Seller clicks "Connect Amazon"
3. Seller logs in to Amazon
4. Seller approves permissions
5. Your application receives authorization code
6. Exchange code for tokens (see Step 7)

---

## Step 7: Secure Credential Storage

### For Development

Store in `.env` file (gitignored):

```bash
AMAZON_LWA_CLIENT_ID=amzn1.application-oa2-client.xxxxx
AMAZON_LWA_CLIENT_SECRET=xxxxx
AMAZON_REFRESH_TOKEN=Atzr|xxxxx
AMAZON_MARKETPLACE_ID=ATVPDKIKX0DER
AMAZON_ENVIRONMENT=sandbox
```

### For Production

Use AWS Secrets Manager or similar:

```bash
aws secretsmanager create-secret \
  --name amazon-sp-api-credentials \
  --secret-string '{
    "client_id": "amzn1.application-oa2-client.xxxxx",
    "client_secret": "xxxxx",
    "refresh_token": "Atzr|xxxxx",
    "marketplace_id": "ATVPDKIKX0DER"
  }'
```

---

## Step 8: Test Connection

1. Ensure `MOCK_ONLY=False` in environment
2. Start the application
3. Navigate to Amazon connection settings
4. Click "Test Connection"
5. Verify connection status shows "Connected"

---

## Step 9: Verify Access

1. Check that orders are being fetched
2. Verify order data matches sandbox/test data
3. Confirm no errors in logs
4. Verify audit events are recorded

---

## What NOT to Enable Yet

| Feature | Status | Reason |
|---------|--------|--------|
| Production endpoints | ❌ Not yet | Wait for CHUNK 1W |
| PII access (buyer info) | ❌ Not yet | Requires additional approval |
| Shipment confirmation | ❌ Not yet | Requires additional approval |
| Order modification | ❌ Never | Out of scope |
| Order cancellation | ❌ Never | Out of scope |

---

## How to Revoke Access

1. Log in to Seller Central
2. Go to "Apps & Services" → "Develop Apps"
3. Find the application
4. Click "Revoke" or "Disconnect"
5. Confirm revocation

**Note**: Revoking access stops all API calls immediately.

---

## How to Rotate Credentials

1. Log in to Amazon Developer Portal
2. Navigate to your application
3. Find "LWA Credentials"
4. Click "Rotate" or "Regenerate"
5. Update your application with new credentials
6. Test connection with new credentials

**Amazon requires credential rotation every 180 days.**

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Invalid client_id" | Check LWA Client ID is correct |
| "Invalid_client_secret" | Check LWA Client Secret is correct |
| "Invalid_grant" | Refresh token may be expired or revoked |
| "Unauthorized" | Check roles are approved |
| "Rate limited" | Wait and retry (5 req/s limit) |
| "Sandbox not available" | Verify using sandbox endpoints |
