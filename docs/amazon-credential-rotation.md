# Amazon Credential Rotation Guide

## Overview

This guide covers rotating Amazon SP-API credentials (LWA Client ID, Client Secret, and Refresh Token).

## When to Rotate

### Scheduled Rotation

Rotate credentials every **90 days** as a security best practice.

### Emergency Rotation

Rotate immediately if:

- Credentials may have been compromised
- Refresh token is revoked
- Unusual API activity detected
- Security incident reported

## Rotation Procedure

### Step 1: Generate New Credentials

1. Log in to Amazon Developer Console
2. Navigate to your application
3. Go to "OAuth Credentials"
4. Click "Generate New Credentials"
5. **Save the new Client ID and Client Secret immediately** — they cannot be retrieved later

### Step 2: Get New Refresh Token

1. Navigate to "Authorization"
2. Click "Authorize Application"
3. Complete OAuth flow
4. Copy the new Refresh Token

### Step 3: Update Secrets Manager

```bash
# AWS Secrets Manager
aws secretsmanager update-secret \
  --secret-id amazon-sp-api/production \
  --secret-string '{
    "client_id": "new_client_id",
    "client_secret": "new_client_secret",
    "refresh_token": "new_refresh_token"
  }'
```

### Step 4: Restart Application

```bash
# Option 1: Restart the service
systemctl restart amazon-fulfillment

# Option 2: Wait for next token refresh
# Tokens auto-refresh, so new credentials take effect on next refresh
```

### Step 5: Verify

```bash
# Check status
curl http://localhost:8000/api/v1/amazon/status

# Expected
{
  "configured": true,
  "environment": "production",
  "token_refresh_count": 0  # Reset after rotation
}
```

### Step 6: Revoke Old Credentials

1. Log in to Amazon Developer Console
2. Navigate to "OAuth Credentials"
3. Revoke old Client Secret
4. Confirm revocation

## Rollback

If new credentials fail:

1. Restore old credentials in Secrets Manager
2. Restart application
3. Verify connection

## Monitoring

After rotation, monitor for:

- Authentication failures
- Token refresh errors
- API call failures

## Security Notes

- ✅ Never log credentials during rotation
- ✅ Never commit credentials to git
- ✅ Use Secrets Manager for all credentials
- ✅ Verify connection after rotation
- ✅ Revoke old credentials after verification
