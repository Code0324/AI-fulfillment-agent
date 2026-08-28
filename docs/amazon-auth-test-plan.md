# Amazon Authentication Security Test Plan

## CHUNK 1T — Amazon LWA Credentials & Authentication Architecture Review

Future tests for authentication security. These are **test plans only** — not implemented yet.

---

## Test Categories

### 1. Secret Leakage Tests

| Test | Description | Expected |
|------|-------------|----------|
| `test_no_credentials_in_logs` | Verify no credentials appear in log output | Pass |
| `test_no_credentials_in_error_messages` | Verify credentials stripped from exceptions | Pass |
| `test_no_credentials_in_api_responses` | Verify credentials not returned to frontend | Pass |
| `test_no_credentials_in_audit_events` | Verify audit logs use redacted values | Pass |
| `test_no_credentials_in_database` | Verify credentials encrypted at rest | Pass |
| `test_no_credentials_in_git` | Verify .env in .gitignore | Pass |

### 2. Token Leakage Tests

| Test | Description | Expected |
|------|-------------|----------|
| `test_access_token_not_in_response` | Verify access token not in API response | Pass |
| `test_refresh_token_not_in_response` | Verify refresh token not in API response | Pass |
| `test_access_token_not_in_logs` | Verify access token redacted in logs | Pass |
| `test_refresh_token_not_in_logs` | Verify refresh token redacted in logs | Pass |
| `test_token_not_in_exception` | Verify tokens stripped from exceptions | Pass |

### 3. Tenant Isolation Tests

| Test | Description | Expected |
|------|-------------|----------|
| `test_tenant_a_cannot_see_tenant_b_orders` | Verify order isolation | Pass |
| `test_tenant_a_cannot_use_tenant_b_tokens` | Verify token isolation | Pass |
| `test_tenant_a_cannot_access_tenant_b_connection` | Verify connection isolation | Pass |
| `test_cross_tenant_request_rejected` | Verify cross-tenant API calls fail | Pass |

### 4. Authorization Failure Tests

| Test | Description | Expected |
|------|-------------|----------|
| `test_invalid_auth_code_rejected` | Verify invalid codes are rejected | Pass |
| `test_expired_auth_code_rejected` | Verify expired codes are rejected | Pass |
| `test_used_auth_code_rejected` | Verify replay of used codes fails | Pass |
| `test_wrong_client_id_rejected` | Verify mismatched client ID fails | Pass |

### 5. Token Expiration Tests

| Test | Description | Expected |
|------|-------------|----------|
| `test_expired_access_token_triggers_refresh` | Verify auto-refresh on expiry | Pass |
| `test_refresh_token_expiry_marks_needs_reauth` | Verify expired refresh token handled | Pass |
| `test_token_refresh_within_buffer` | Verify refresh happens before expiry | Pass |

### 6. Refresh Failure Tests

| Test | Description | Expected |
|------|-------------|----------|
| `test_refresh_with_invalid_refresh_token` | Verify error handled safely | Pass |
| `test_refresh_with_revoked_refresh_token` | Verify marks needs_reauth | Pass |
| `test_concurrent_refresh_safe` | Verify no race conditions | Pass |
| `test_refresh_failure_does_not_corrupt_state` | Verify state integrity | Pass |

### 7. Revoked Authorization Tests

| Test | Description | Expected |
|------|-------------|----------|
| `test_revoked_authorization_stops_api_calls` | Verify API calls stop | Pass |
| `test_revoked_authorization_notifies_user` | Verify user notification | Pass |
| `test_revoked_authorization_requires_reauth` | Verify reauth required | Pass |

### 8. CSRF/State Validation Tests

| Test | Description | Expected |
|------|-------------|----------|
| `test_invalid_state_token_rejected` | Verify CSRF protection | Pass |
| `test_expired_state_token_rejected` | Verify state expiry enforced | Pass |
| `test_reused_state_token_rejected` | Verify replay prevention | Pass |
| `test_state_bound_to_session` | Verify session binding | Pass |

### 9. Redirect URI Validation Tests

| Test | Description | Expected |
|------|-------------|----------|
| `test_invalid_redirect_uri_rejected` | Verify URI validation | Pass |
| `test_non_https_rejected_in_production` | Verify HTTPS requirement | Pass |
| `test_wildcard_uri_rejected` | Verify no wildcards allowed | Pass |

### 10. Permission Enforcement Tests

| Test | Description | Expected |
|------|-------------|----------|
| `test_viewer_cannot_trigger_import` | Verify role enforcement | Pass |
| `test_operator_cannot_manage_credentials` | Verify role enforcement | Pass |
| `test_manager_cannot_view_raw_credentials` | Verify credential access control | Pass |
| `test_unauthenticated_rejected` | Verify auth required | Pass |

### 11. Audit Redaction Tests

| Test | Description | Expected |
|------|-------------|----------|
| `test_audit_log_redacts_credentials` | Verify credential redaction | Pass |
| `test_audit_log_redacts_tokens` | Verify token redaction | Pass |
| `test_audit_log_redacts_pii` | Verify PII redaction | Pass |

### 12. Frontend Token Exposure Tests

| Test | Description | Expected |
|------|-------------|----------|
| `test_connection_status_endpoint_no_tokens` | Verify status endpoint safe | Pass |
| `test_sync_status_endpoint_no_tokens` | Verify sync endpoint safe | Pass |
| `test_error_endpoint_no_tokens` | Verify error endpoint safe | Pass |

### 13. Credential Access Control Tests

| Test | Description | Expected |
|------|-------------|----------|
| `test_only_admin_can_view_connection_details` | Verify admin-only access | Pass |
| `test_only_admin_can_disconnect` | Verify admin-only disconnect | Pass |
| `test_credential_endpoint_requires_auth` | Verify auth required | Pass |
| `test_credential_endpoint_requires_role` | Verify role required | Pass |

---

## Existing Mock/Security Tests

The following tests already exist and verify current security behavior:

| Test File | Tests | Status |
|-----------|-------|--------|
| `test_provider_contract.py` | 71 tests | ✅ Passing |
| `test_mock_amazon.py` | 63 tests | ✅ Passing |
| `test_fulfillment_safety.py` | Existing | ✅ Passing |

---

## Test Execution Strategy

1. **Unit tests**: Run with every commit
2. **Integration tests**: Run before deployment
3. **Security tests**: Run weekly + before release
4. **Penetration testing**: Annual third-party review
