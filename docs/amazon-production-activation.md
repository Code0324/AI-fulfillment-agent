# Amazon Production Activation Guide

## Overview

This guide explains how to activate Amazon SP-API production integration. The software is **technically ready** — this guide covers the operational steps to go live.

## Prerequisites

Before activating production:

1. ✅ Amazon SP-API integration implemented
2. ✅ LWA authentication implemented
3. ✅ Read-only operations enforced
4. ✅ Production-readiness review complete
5. ❌ Amazon developer account needed
6. ❌ SP-API application needed
7. ❌ LWA credentials needed

## Step 1: Register Amazon Developer Account

1. Go to https://developer.amazonservices.com
2. Click "Register"
3. Complete developer registration
4. Verify email address
5. Accept Amazon SP-API terms

## Step 2: Create SP-API Application

1. Log in to Amazon Developer Console
2. Navigate to "Applications"
3. Click "Create New Application"
4. Fill in application details:
   - Application Name
   - Application Description
   - Application Logo (optional)
5. Save application

## Step 3: Configure OAuth Credentials

1. In your application, navigate to "OAuth Credentials"
2. Generate Client ID and Client Secret
3. **IMPORTANT**: Save these securely — they cannot be retrieved later

## Step 4: Request Required Roles

Navigate to "Application Permissions" and request:

- **Orders API**: `sellingpartnerapi::orders` (read-only)
- **PII Permissions** (if needed): Submit use case for Personally Identifiable Information

Wait for Amazon approval (typically 2-7 business days).

## Step 5: Get Refresh Token

1. Navigate to "Authorization"
2. Click "Authorize Application"
3. Complete OAuth flow
4. Copy the Refresh Token

## Step 6: Store Credentials Securely

### Option A: Environment Variables

```bash
export AMAZON_LWA_CLIENT_ID="your_client_id_here"
export AMAZON_LWA_CLIENT_SECRET="your_client_secret_here"
export AMAZON_LWA_REFRESH_TOKEN="your_refresh_token_here"
export AMAZON_ENVIRONMENT="production"
export AMAZON_SP_API_REGION="na"
export AMAZON_MARKETPLACE_ID="ATVPDKIKX0DER"
```

### Option B: Secrets Manager (Recommended for Production)

Store credentials in AWS Secrets Manager, Azure Key Vault, or similar:

```
Secret Name: amazon-sp-api/production
Keys:
  - client_id
  - client_secret
  - refresh_token
```

## Step 7: Update Configuration

Set environment variables:

```bash
# Required for production
AMAZON_ENVIRONMENT=production

# Credentials (from Secrets Manager)
AMAZON_LWA_CLIENT_ID=<from_secrets>
AMAZON_LWA_CLIENT_SECRET=<from_secrets>
AMAZON_LWA_REFRESH_TOKEN=<from_secrets>

# Optional (defaults shown)
AMAZON_SP_API_REGION=na
AMAZON_MARKETPLACE_ID=ATVPDKIKX0DER
```

## Step 8: Verify Connection

```bash
# Check status
curl http://localhost:8000/api/v1/amazon/status

# Expected response
{
  "configured": true,
  "sandbox": false,
  "environment": "production",
  "mode": "read-only"
}
```

## Step 9: Test with Production

1. Verify connection status shows `environment: "production"`
2. Test order retrieval with a real order
3. Verify PII is properly handled
4. Monitor error rates

## Troubleshooting

### Issue: "BLOCKED: Production endpoint detected"

**Cause**: `AMAZON_ENVIRONMENT` is not set to `production`
**Fix**: Set `AMAZON_ENVIRONMENT=production`

### Issue: "AMAZON_ENVIRONMENT=production but credentials not configured"

**Cause**: Missing one or more LWA credentials
**Fix**: Verify all three credentials are set:
- `AMAZON_LWA_CLIENT_ID`
- `AMAZON_LWA_CLIENT_SECRET`
- `AMAZON_LWA_REFRESH_TOKEN`

### Issue: "LWA authentication failed: invalid_grant"

**Cause**: Refresh token expired or revoked
**Fix**: Re-authorize application and get new refresh token

### Issue: "LWA authentication failed: invalid_client"

**Cause**: Invalid client ID or secret
**Fix**: Verify credentials in Amazon Developer Console

## Rollback

To rollback to sandbox:

```bash
export AMAZON_ENVIRONMENT=sandbox
```

Or remove production credentials:

```bash
unset AMAZON_LWA_CLIENT_ID
unset AMAZON_LWA_CLIENT_SECRET
unset AMAZON_LWA_REFRESH_TOKEN
unset AMAZON_ENVIRONMENT
```

System will automatically fall back to mock-only mode.

## Security Notes

- ✅ Credentials are never logged
- ✅ Tokens are memory-only
- ✅ PII is anonymized
- ✅ Read-only operations only
- ✅ Approval gate is mandatory
- ✅ No write operations enabled

## Next Steps

After production activation:

1. Monitor API usage and error rates
2. Set up alerts for authentication failures
3. Implement credential rotation procedure
4. Document operational runbook
