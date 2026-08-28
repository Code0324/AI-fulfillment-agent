# Amazon Emergency Disconnect Guide

## Overview

This guide covers emergency procedures to disconnect from Amazon SP-API production.

## When to Emergency Disconnect

### Immediate Disconnect Required

- Security breach detected
- Credentials compromised
- Unusual API activity
- Amazon account suspended
- Regulatory compliance requirement

### Planned Disconnect

- Maintenance window
- Credential rotation
- Environment migration

## Immediate Disconnect Procedure

### Step 1: Remove Credentials

```bash
# Remove all Amazon credentials from environment
unset AMAZON_LWA_CLIENT_ID
unset AMAZON_LWA_CLIENT_SECRET
unset AMAZON_LWA_REFRESH_TOKEN
unset AMAZON_ENVIRONMENT
```

### Step 2: Restart Application

```bash
# Restart the backend service
systemctl restart amazon-fulfillment

# Or if running manually
# Kill the process and restart without credentials
```

### Step 3: Verify Disconnect

```bash
# Check status
curl http://localhost:8000/api/v1/amazon/status

# Expected response
{
  "configured": false,
  "sandbox": true,
  "environment": "sandbox",
  "mode": "read-only",
  "notice": "Amazon provider not registered — no credentials available"
}
```

### Step 4: Confirm Mock-Only Mode

```bash
# Check provider list
curl http://localhost:8000/api/v1/providers

# Expected
{
  "providers": [...],
  "mock_only": true,
  "environment": "sandbox",
  "notice": "All providers are LOCAL/MOCK implementations only"
}
```

## System Behavior After Disconnect

### What Works

- ✅ All local operations
- ✅ Mock order processing
- ✅ Fulfillment engine (with mock data)
- ✅ Address processing
- ✅ Inventory management
- ✅ Approval gate

### What Doesn't Work

- ❌ Amazon order retrieval
- ❌ Amazon order import
- ❌ Live Amazon connection

### Data Safety

- ✅ No data loss (all operations are local)
- ✅ Existing orders preserved
- ✅ Fulfillment state preserved
- ✅ Inventory state preserved

## Reconnection Procedure

### Step 1: Verify Credentials

Ensure you have valid credentials:

- Client ID
- Client Secret
- Refresh Token

### Step 2: Set Environment Variables

```bash
export AMAZON_ENVIRONMENT=production
export AMAZON_LWA_CLIENT_ID="your_client_id"
export AMAZON_LWA_CLIENT_SECRET="your_client_secret"
export AMAZON_LWA_REFRESH_TOKEN="your_refresh_token"
```

### Step 3: Restart Application

```bash
systemctl restart amazon-fulfillment
```

### Step 4: Verify Connection

```bash
curl http://localhost:8000/api/v1/amazon/status

# Expected
{
  "configured": true,
  "environment": "production",
  "mode": "read-only"
}
```

## Incident Response

### If Credentials Compromised

1. **Immediately**: Remove credentials (Step 1)
2. **Notify**: Security team
3. **Rotate**: Generate new credentials
4. **Verify**: New credentials work
5. **Revoke**: Old credentials in Amazon Developer Console
6. **Audit**: Review API logs for unauthorized access

### If Amazon Account Suspended

1. **Immediately**: Remove credentials (Step 1)
2. **Contact**: Amazon Developer Support
3. **Resolve**: Account suspension issue
4. **Reconnect**: Follow reconnection procedure

## Monitoring During Disconnect

After emergency disconnect, monitor:

- Application logs for errors
- User reports of issues
- Amazon Developer Console for account status

## Security Checklist

- [ ] Credentials removed from environment
- [ ] Application restarted
- [ ] Mock-only mode confirmed
- [ ] No data loss verified
- [ ] Incident documented
- [ ] Team notified (if applicable)
