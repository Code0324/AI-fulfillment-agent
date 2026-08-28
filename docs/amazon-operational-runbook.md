# Amazon Operational Runbook

## Overview

This runbook covers operational procedures for the Amazon SP-API integration.

## Daily Operations

### 1. Health Check

```bash
# Check backend health
curl http://localhost:8000/health

# Check Amazon connection status
curl http://localhost:8000/api/v1/amazon/status
```

Expected response:
```json
{
  "configured": true,
  "sandbox": true,
  "environment": "sandbox",
  "mode": "read-only"
}
```

### 2. Token Health

Check token expiration:
```bash
curl http://localhost:8000/api/v1/amazon/status | jq '.token_expires_in'
```

Tokens auto-refresh 5 minutes before expiry. No manual intervention needed.

### 3. Request Statistics

Monitor API usage:
```bash
curl http://localhost:8000/api/v1/amazon/status | jq '.request_stats'
```

Watch for:
- High failure rates
- Rate limit violations (429 errors)

## Common Issues

### Issue 1: Authentication Failed

**Symptoms**: `LWAAuthenticationError: invalid_client`
**Cause**: Invalid or expired credentials
**Resolution**:
1. Verify credentials in environment
2. Check if credentials need rotation
3. Regenerate credentials if needed

### Issue 2: Rate Limited

**Symptoms**: `SPAPIError: 429 Too Many Requests`
**Cause**: Exceeded rate limits
**Resolution**:
1. Wait for rate limit window to reset
2. Implement request batching
3. Monitor request frequency

### Issue 3: Token Expired

**Symptoms**: `LWAAuthenticationError: refresh token is invalid or revoked`
**Cause**: Refresh token expired or revoked
**Resolution**:
1. Re-authorize application
2. Obtain new refresh token
3. Update credentials

### Issue 4: Production Endpoint Blocked

**Symptoms**: `SPAPIError: BLOCKED: Production endpoint detected`
**Cause**: Attempting to use production endpoints
**Resolution**:
1. Verify `AMAZON_ENVIRONMENT` is not set to `production`
2. Check for code changes that might enable production
3. Review security settings

## Monitoring Alerts

### Critical Alerts

| Alert | Threshold | Action |
|-------|-----------|--------|
| Auth failures | > 5 in 5 min | Check credentials |
| API errors | > 10% rate | Investigate root cause |
| Rate limits | > 3 in 1 min | Reduce request frequency |

### Warning Alerts

| Alert | Threshold | Action |
|-------|-----------|--------|
| Token expiry | < 10 min | Verify auto-refresh |
| Slow responses | > 5s avg | Check network/Amazon status |

## Maintenance Procedures

### Credential Rotation

1. Generate new credentials in Amazon Developer Console
2. Update secrets manager
3. Restart application (or wait for next token refresh)
4. Verify connection status

### Code Updates

1. Run full test suite: `pytest tests/`
2. Run frontend checks: `tsc --noEmit && npm run lint && npm run build`
3. Deploy to staging first
4. Verify all endpoints working
5. Deploy to production

### Backup/Recovery

**Backup**: No persistent state to backup (in-memory only)
**Recovery**: Restart application — all data is re-fetched from Amazon

## Escalation

| Severity | Response Time | Escalation |
|----------|---------------|------------|
| Critical | 1 hour | Immediate |
| High | 4 hours | Same day |
| Medium | 24 hours | Next business day |

## Contact Information

- **Amazon SP-API Support**: https://sellercentral.amazon.com/support
- **Developer Forums**: https://sellercentral.amazon.com/forums
- **Internal Team**: [Your team contact]
