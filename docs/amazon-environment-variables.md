# Amazon Environment Variables

## CHUNK 1U — Official Amazon Sandbox / Developer Environment

---

## Environment Variable Structure

### Required Variables (Future)

| Variable | Purpose | Required | Default |
|----------|---------|----------|---------|
| `AMAZON_LWA_CLIENT_ID` | LWA application identifier | Yes (when enabled) | None |
| `AMAZON_LWA_CLIENT_SECRET` | LWA application secret | Yes (when enabled) | None |
| `AMAZON_REFRESH_TOKEN` | LWA refresh token | Yes (when enabled) | None |
| `AMAZON_MARKETPLACE_ID` | Target marketplace | Yes | `ATVPDKIKX0DER` (US) |
| `AMAZON_SELLER_ID` | Seller account identifier | Yes (multi-tenant) | None |
| `AMAZON_ENVIRONMENT` | Environment selector | Yes | `sandbox` |
| `AMAZON_REDIRECT_URI` | OAuth callback URI | Yes (for OAuth) | None |
| `AMAZON_REGION` | API region | Yes | `na` (North America) |

### Optional Variables

| Variable | Purpose | Required | Default |
|----------|---------|----------|---------|
| `AMAZON_APP_TYPE` | Application type (public/private) | No | `private` |
| `AMAZON_RATE_LIMIT_RPS` | Rate limit (requests/second) | No | `5` |
| `AMAZON_RATE_LIMIT_BURST` | Rate limit burst | No | `15` |

### Safety Variables

| Variable | Purpose | Required | Default |
|----------|---------|----------|---------|
| `MOCK_ONLY` | Global safety flag | Yes | `True` |

---

## Environment-Specific Configuration

### Development (.env)

```bash
# Amazon SP-API Configuration (Development/Sandbox)
AMAZON_LWA_CLIENT_ID=amzn1.application-oa2-client-dev.xxxxx
AMAZON_LWA_CLIENT_SECRET=xxxxx
AMAZON_REFRESH_TOKEN=Atzr|xxxxx
AMAZON_MARKETPLACE_ID=ATVPDKIKX0DER
AMAZON_SELLER_ID=dev-seller-id
AMAZON_ENVIRONMENT=sandbox
AMAZON_REDIRECT_URI=http://localhost:8000/api/v1/amazon/callback
AMAZON_REGION=na

# Safety
MOCK_ONLY=True
```

### Production

```bash
# All credentials from Secrets Manager
# No credentials in environment variables
AMAZON_MARKETPLACE_ID=ATVPDKIKX0DER
AMAZON_ENVIRONMENT=production
AMAZON_REGION=na

# Safety
MOCK_ONLY=False  # Only when explicitly enabled
```

---

## .env.example (Placeholder)

```bash
# Amazon SP-API Configuration
# DO NOT put real credentials here
AMAZON_LWA_CLIENT_ID=your-client-id-here
AMAZON_LWA_CLIENT_SECRET=your-client-secret-here
AMAZON_REFRESH_TOKEN=your-refresh-token-here
AMAZON_MARKETPLACE_ID=ATVPDKIKX0DER
AMAZON_SELLER_ID=your-seller-id-here
AMAZON_ENVIRONMENT=sandbox
AMAZON_REDIRECT_URI=http://localhost:8000/api/v1/amazon/callback
AMAZON_REGION=na

# Safety
MOCK_ONLY=True
```

---

## .gitignore Entries

```
# Amazon credentials
.env
.env.local
.env.production
*.env

# Never commit these
AMAZON_LWA_CLIENT_SECRET
AMAZON_REFRESH_TOKEN
```

---

## Variable Validation

Future validation should check:

1. **Required variables present**: All required variables must be set when AMAZON_ENVIRONMENT is not `mock`
2. **Format validation**: Client ID, secret, tokens must match expected formats
3. **Region validation**: Must be one of `na`, `eu`, `fe`
4. **Marketplace validation**: Must be valid Amazon marketplace ID
5. **MOCK_ONLY enforcement**: If MOCK_ONLY=True, Amazon credentials should be ignored

---

## Credential Safety Rules

| Rule | Description |
|------|-------------|
| Never in source code | Credentials never in .py, .ts, .tsx, .json, .yaml |
| Never in git | .env files gitignored |
| Never in logs | Credentials redacted in all log output |
| Never in errors | Credentials stripped from exception messages |
| Never in frontend | Credentials never sent to browser |
| Never in tests | Test fixtures use mock credentials only |
| Never in audit | Audit logs use redacted values only |
