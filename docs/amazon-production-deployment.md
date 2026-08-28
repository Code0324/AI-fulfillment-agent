# Amazon Production Deployment Guide

## Overview

This guide covers deploying the Amazon AI Fulfillment Assistant with production Amazon SP-API integration.

## Deployment Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Load Balancer (HTTPS)                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Application Server                         │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Backend (FastAPI)                                     │  │
│  │  ├── Amazon SP-API Client (Read-Only)                  │  │
│  │  ├── LWA Authentication (Memory-Only Tokens)           │  │
│  │  ├── Order Service (In-Memory)                         │  │
│  │  ├── Fulfillment Engine                                │  │
│  │  └── Approval Gate                                     │  │
│  └───────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Frontend (Next.js)                                    │  │
│  │  ├── Dashboard                                         │  │
│  │  ├── Amazon Status                                     │  │
│  │  └── Order Management                                  │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Secrets Manager                           │
│  ├── AMAZON_LWA_CLIENT_ID                                   │
│  ├── AMAZON_LWA_CLIENT_SECRET                               │
│  └── AMAZON_LWA_REFRESH_TOKEN                               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Amazon SP-API                             │
│  ├── LWA Auth: https://api.amazon.com/auth/o2/token        │
│  └── Orders API: sellingpartnerapi-na.amazon.com            │
└─────────────────────────────────────────────────────────────┘
```

## Environment Variables

### Required for Production

| Variable | Description | Example |
|----------|-------------|---------|
| `AMAZON_ENVIRONMENT` | Set to `production` | `production` |
| `AMAZON_LWA_CLIENT_ID` | Amazon SP-API Client ID | `amzn1.application-oa2-client.xxxx` |
| `AMAZON_LWA_CLIENT_SECRET` | Amazon SP-API Client Secret | `secret_value_here` |
| `AMAZON_LWA_REFRESH_TOKEN` | LWA Refresh Token | `Atzr\|xxxx` |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `AMAZON_SP_API_REGION` | `na` | Region: `na`, `eu`, `fe` |
| `AMAZON_MARKETPLACE_ID` | `ATVPDKIKX0DER` | US Marketplace |
| `APP_ENV` | `development` | Application environment |
| `BACKEND_HOST` | `0.0.0.0` | Backend host |
| `BACKEND_PORT` | `8000` | Backend port |

## Deployment Steps

### 1. Prepare Secrets

```bash
# Using AWS Secrets Manager
aws secretsmanager create-secret \
  --name amazon-sp-api/production \
  --secret-string '{
    "client_id": "your_client_id",
    "client_secret": "your_client_secret",
    "refresh_token": "your_refresh_token"
  }'
```

### 2. Configure Environment

```bash
# Production environment
export AMAZON_ENVIRONMENT=production
export AMAZON_SP_API_REGION=na
export AMAZON_MARKETPLACE_ID=ATVPDKIKX0DER

# Load from Secrets Manager
aws secretsmanager get-secret-value \
  --secret-id amazon-sp-api/production \
  --query 'SecretString' \
  --output text | jq -r 'to_entries[] | "\(.key)=\(.value)"' | while read line; do
    export "AMAZON_LWA_$(echo $line | cut -d= -f1 | tr '[:lower:]' '[:upper:]')=$(echo $line | cut -d= -f2)"
done
```

### 3. Build and Deploy

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Frontend
cd frontend
npm install
npm run build
npm start
```

### 4. Verify Deployment

```bash
# Check health
curl http://localhost:8000/health

# Check Amazon status
curl http://localhost:8000/api/v1/amazon/status

# Expected
{
  "configured": true,
  "sandbox": false,
  "environment": "production",
  "mode": "read-only"
}
```

## Security Checklist

- [ ] Secrets stored in Secrets Manager (not in code)
- [ ] HTTPS enabled for all endpoints
- [ ] No credentials in logs
- [ ] No credentials in frontend
- [ ] Read-only operations enforced
- [ ] Approval gate mandatory
- [ ] PII protection active

## Monitoring

### Key Metrics

1. **LWA Token Health**
   - Token refresh success rate
   - Token expiration alerts

2. **API Call Metrics**
   - Request counts
   - Error rates
   - Latency

3. **Security Events**
   - Failed authentication attempts
   - Rate limit violations

### Alerts

| Alert | Threshold | Action |
|-------|-----------|--------|
| Auth failures | > 5 in 5 min | Check credentials |
| API errors | > 10% rate | Investigate |
| Rate limits | > 3 in 1 min | Reduce frequency |

## Rollback Procedure

### Immediate Rollback

```bash
# Switch to sandbox
export AMAZON_ENVIRONMENT=sandbox

# Or remove credentials
unset AMAZON_LWA_CLIENT_ID
unset AMAZON_LWA_CLIENT_SECRET
unset AMAZON_LWA_REFRESH_TOKEN
unset AMAZON_ENVIRONMENT
```

### Code Rollback

```bash
# Revert to previous version
git checkout <previous_commit>
# Redeploy
```

## Credential Rotation

### Procedure

1. Generate new credentials in Amazon Developer Console
2. Update Secrets Manager with new values
3. Restart application (or wait for next token refresh)
4. Verify connection status

### Timeline

- **Before expiry**: Rotate 7 days before expiration
- **Emergency**: Rotate immediately if compromised

## Emergency Disconnect

### Immediate Actions

1. Remove credentials from environment
2. System falls back to mock-only mode
3. No data loss (all operations are local)
4. Investigate incident

### Commands

```bash
# Remove all Amazon credentials
unset AMAZON_LWA_CLIENT_ID
unset AMAZON_LWA_CLIENT_SECRET
unset AMAZON_LWA_REFRESH_TOKEN
unset AMAZON_ENVIRONMENT

# Restart application
# System will run in mock-only mode
```

## Troubleshooting

See `docs/amazon-production-activation.md` for common issues and solutions.
