# Amazon Release Checklist

## Pre-Production Checklist

### Code Quality
- [x] All tests passing (661 tests)
- [x] TypeScript compilation clean
- [x] ESLint clean
- [x] Build successful
- [x] No security warnings

### Security
- [x] No hardcoded credentials
- [x] No credentials in frontend
- [x] No credentials in tests
- [x] Production endpoints blocked
- [x] PII protection active
- [x] Approval gate mandatory

### Architecture
- [x] Provider abstraction intact
- [x] Fulfillment engine provider-agnostic
- [x] Amazon logic isolated
- [x] Mock providers working
- [x] OrderService authoritative

### Documentation
- [x] Production readiness doc
- [x] Security review doc
- [x] Release checklist (this file)
- [x] Operational runbook

## Operational Setup (Required Before Production)

### 1. Amazon Developer Account
- [ ] Register at https://developer.amazonservices.com
- [ ] Verify developer account
- [ ] Review Amazon SP-API terms

### 2. SP-API Application
- [ ] Create new application
- [ ] Configure application details
- [ ] Request required permissions:
  - [ ] Orders API (read)
  - [ ] PII permissions (if needed)
- [ ] Wait for application approval

### 3. LWA Credentials
- [ ] Generate Client ID
- [ ] Generate Client Secret
- [ ] Obtain Refresh Token
- [ ] Store in secrets manager

### 4. Production Configuration
- [ ] Set environment variables:
  ```
  AMAZON_LWA_CLIENT_ID=<from_aws_secrets>
  AMAZON_LWA_CLIENT_SECRET=<from_aws_secrets>
  AMAZON_LWA_REFRESH_TOKEN=<from_aws_secrets>
  AMAZON_SP_API_REGION=na
  AMAZON_MARKETPLACE_ID=ATVPDKIKX0DER
  ```
- [ ] Verify secrets manager access
- [ ] Test credential rotation

### 5. Production Code Changes
- [ ] Add production endpoints to SPAPIClient
- [ ] Modify `_validate_endpoint` for production
- [ ] Add `AMAZON_ENVIRONMENT` config
- [ ] Update error messages for production

### 6. Monitoring Setup
- [ ] Configure LWA token health monitoring
- [ ] Set up API call metrics
- [ ] Configure error rate alerts
- [ ] Set up rate limit monitoring

### 7. Deployment
- [ ] Deploy to staging environment
- [ ] Test with sandbox credentials
- [ ] Verify all endpoints working
- [ ] Run full test suite
- [ ] Deploy to production

### 8. Post-Deployment
- [ ] Verify production connection
- [ ] Test order retrieval
- [ ] Monitor error rates
- [ ] Verify approval gate
- [ ] Document any issues

## Rollback Procedure

If issues occur after deployment:

1. **Immediate**: Remove production credentials from environment
2. **System**: Falls back to mock-only mode automatically
3. **Data**: No data loss (all operations are local)
4. **Approval**: Fulfillment requires manual approval (safe by default)

## Sign-Off

| Reviewer | Date | Status |
|----------|------|--------|
| Security | | ⬜ Pending |
| Operations | | ⬜ Pending |
| Development | | ⬜ Pending |

## Notes

- This checklist is for **operational setup**, not code changes
- The software is **technically ready** — these are deployment steps
- No code modifications required for production (except enabling endpoints)
