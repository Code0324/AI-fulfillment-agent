# Amazon Human Activation Checklist

## Overview

This checklist guides you through activating Amazon SP-API production integration. Every step requires **human action** — the software cannot complete these steps automatically.

## Pre-Activation Status

```
SOFTWARE READY:    ✅
CREDENTIALS READY: ❌ (you must provide these)
AMAZON ACCOUNT:    ❌ (you must create this)
LIVE CONNECTION:   ❌ (will be verified after activation)
PRODUCTION DEPLOY: ❌ (will be done after verification)
```

---

## Step 1: Amazon Developer Registration

**Time required:** 10-15 minutes
**Who:** You (account owner)

### Actions

1. Go to https://developer.amazonservices.com
2. Click **"Register"** or **"Sign Up"**
3. Fill in developer information:
   - Company name
   - Contact email
   - Phone number
4. Accept Amazon SP-API Terms of Service
5. Verify email address

### Verification

- [ ] Email verified
- [ ] Developer account active
- [ ] Can log in to Developer Console

---

## Step 2: SP-API Application Creation

**Time required:** 10-15 minutes
**Who:** You (developer)

### Actions

1. Log in to Amazon Developer Console
2. Navigate to **"Applications"**
3. Click **"Create New Application"**
4. Fill in application details:
   - **Application Name**: e.g., "Amazon AI Fulfillment Assistant"
   - **Application Description**: "Read-only order integration for fulfillment"
   - **Application Logo**: Optional
5. Click **"Save"**

### Verification

- [ ] Application created
- [ ] Application ID visible
- [ ] Application status: Active

---

## Step 3: OAuth Credentials

**Time required:** 5 minutes
**Who:** You (developer)

### Actions

1. In your application, navigate to **"OAuth Credentials"**
2. Click **"Generate New Credentials"**
3. **SAVE IMMEDIATELY** (cannot be retrieved later):
   - Client ID
   - Client Secret
4. Store securely (password manager recommended)

### Verification

- [ ] Client ID saved
- [ ] Client Secret saved
- [ ] Credentials stored securely

---

## Step 4: Request Required Roles

**Time required:** 2-7 business days (Amazon review)
**Who:** You (developer)

### Actions

1. Navigate to **"Application Permissions"**
2. Request the following roles:
   - **Orders API**: `sellingpartnerapi::orders` (read-only)
3. For PII access (if needed):
   - Submit use case for Personally Identifiable Information
   - Explain why PII is needed for fulfillment

### Verification

- [ ] Orders API role requested
- [ ] Role approved by Amazon
- [ ] PII access approved (if needed)

---

## Step 5: LWA Authorization

**Time required:** 5 minutes
**Who:** You (developer)

### Actions

1. Navigate to **"Authorization"**
2. Click **"Authorize Application"**
3. Complete OAuth flow:
   - Log in with Amazon seller account
   - Grant permissions
   - Copy the **Refresh Token**
4. Store Refresh Token securely

### Verification

- [ ] Refresh Token obtained
- [ ] Refresh Token stored securely
- [ ] Authorization complete

---

## Step 6: Secure Credential Storage

**Time required:** 15-30 minutes
**Who:** You (DevOps/Security)

### Actions

Choose one option:

#### Option A: Environment Variables (Development)

```bash
# Add to .env file (DO NOT commit to git)
AMAZON_LWA_CLIENT_ID=your_client_id
AMAZON_LWA_CLIENT_SECRET=your_client_secret
AMAZON_LWA_REFRESH_TOKEN=your_refresh_token
AMAZON_ENVIRONMENT=production
AMAZON_SP_API_REGION=na
AMAZON_MARKETPLACE_ID=ATVPDKIKX0DER
```

#### Option B: Secrets Manager (Production — Recommended)

```bash
# AWS Secrets Manager
aws secretsmanager create-secret \
  --name amazon-sp-api/production \
  --secret-string '{
    "client_id": "your_client_id",
    "client_secret": "your_client_secret",
    "refresh_token": "your_refresh_token"
  }'
```

### Verification

- [ ] Credentials stored securely
- [ ] No credentials in git
- [ ] No credentials in logs
- [ ] Access restricted to authorized personnel

---

## Step 7: Production Environment Configuration

**Time required:** 5 minutes
**Who:** You (DevOps)

### Actions

Set environment variables:

```bash
# Required for production
export AMAZON_ENVIRONMENT=production

# Credentials (from Secrets Manager)
export AMAZON_LWA_CLIENT_ID=<from_secrets>
export AMAZON_LWA_CLIENT_SECRET=<from_secrets>
export AMAZON_LWA_REFRESH_TOKEN=<from_secrets>

# Optional (defaults shown)
export AMAZON_SP_API_REGION=na
export AMAZON_MARKETPLACE_ID=ATVPDKIKX0DER
```

### Verification

- [ ] `AMAZON_ENVIRONMENT=production` set
- [ ] All three LWA credentials set
- [ ] Region and marketplace configured

---

## Step 8: Connection Verification

**Time required:** 5 minutes
**Who:** You (developer)

### Actions

1. Start the application:
   ```bash
   cd backend
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

2. Check connection status:
   ```bash
   curl http://localhost:8000/api/v1/amazon/status
   ```

3. Expected response:
   ```json
   {
     "configured": true,
     "sandbox": false,
     "environment": "production",
     "mode": "read-only"
   }
   ```

### Verification

- [ ] Application started successfully
- [ ] Status shows `configured: true`
- [ ] Status shows `environment: "production"`
- [ ] Status shows `mode: "read-only"`

---

## Step 9: First Read-Only Order Test

**Time required:** 10 minutes
**Who:** You (developer)

### Actions

1. List orders:
   ```bash
   curl http://localhost:8000/api/v1/amazon/orders?limit=5
   ```

2. Check response:
   - Should return list of orders (or empty list if no orders)
   - Should NOT return errors about credentials
   - Should show `sandbox: false` and `environment: "production"`

3. If orders exist, verify:
   - Order IDs are valid Amazon format
   - Addresses are properly formatted
   - No sensitive data exposed

### Verification

- [ ] Orders endpoint responds
- [ ] No authentication errors
- [ ] Orders data properly formatted
- [ ] PII properly handled

---

## Step 10: Rollback/Disconnect Procedure

**Time required:** 2 minutes
**Who:** You (any authorized user)

### Emergency Disconnect

If issues occur:

```bash
# Remove credentials
unset AMAZON_LWA_CLIENT_ID
unset AMAZON_LWA_CLIENT_SECRET
unset AMAZON_LWA_REFRESH_TOKEN
unset AMAZON_ENVIRONMENT

# Restart application
# System falls back to mock-only mode
```

### Verification

- [ ] Disconnect procedure documented
- [ ] Team knows emergency procedure
- [ ] Rollback tested (optional)

---

## Final Status

After completing all steps:

```
SOFTWARE READY:    ✅
CREDENTIALS READY: ✅
AMAZON ACCOUNT:    ✅
LIVE CONNECTION:   ✅ (verified in Step 8)
PRODUCTION DEPLOY: ⬜ (next step)
```

## Post-Activation

1. Monitor API usage and error rates
2. Set up alerts for authentication failures
3. Implement credential rotation schedule
4. Document operational runbook
5. Train team on emergency procedures

## Security Reminders

- ✅ Never share credentials
- ✅ Never commit credentials to git
- ✅ Never log credentials
- ✅ Rotate credentials every 90 days
- ✅ Monitor for unauthorized access
