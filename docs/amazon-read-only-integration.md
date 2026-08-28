# Amazon Read-Only Integration (CHUNK 1V)

## Overview

CHUNK 1V implements a read-only Amazon SP-API sandbox integration. This allows the system to:

1. Connect to Amazon sandbox
2. Retrieve orders via Orders API v2026-01-01
3. Normalize Amazon orders to internal format
4. Import orders for fulfillment processing

**CRITICAL SAFETY:**
- Only sandbox endpoints are accessible
- Production endpoints are blocked at the client level
- Read-only operations only (GET requests)
- All fulfillment requires human approval

## Architecture

```
Amazon Sandbox
      ↓
LWA Authentication
      ↓
AmazonOrderProvider
      ↓
Normalized Order
      ↓
Existing OrderService
      ↓
Existing Fulfillment Engine
      ↓
HUMAN APPROVAL GATE
      ↓
WAITING_APPROVAL
```

## Components

### LWA Authentication (`lwa_auth.py`)

Handles OAuth2 token exchange with Amazon:
- Token acquisition using refresh_token
- Automatic token refresh before expiration
- Token caching in memory only
- Revoked refresh token handling

**Security:**
- Never logs credentials
- Never exposes tokens to external systems
- Tokens are memory-only

### SP-API Client (`sp_api_client.py`)

Amazon SP-API client for sandbox operations:
- Only connects to sandbox endpoints
- Blocks production endpoints
- Implements read-only operations
- Handles rate limiting (1 req/s, burst 15)

**Sandbox Endpoints:**
- North America: `https://sandbox.sellingpartnerapi-na.amazon.com`
- Europe: `https://sandbox.sellingpartnerapi-eu.amazon.com`
- Far East: `https://sandbox.sellingpartnerapi-fe.amazon.com`

### Amazon Order Provider (`order_provider.py`)

Provider implementation for Amazon orders:
- Retrieves orders from Amazon sandbox
- Normalizes Amazon responses to internal format
- Enforces read-only operations
- Handles authentication via LWA

**Operations:**
- `get_order(order_id)` - Get single order
- `list_orders(limit, offset)` - List orders
- `search_orders(...)` - Search with filters
- `import_orders(order_ids)` - Import with idempotency

## Configuration

### Environment Variables

```bash
# LWA Credentials (optional — without these, system runs in mock-only mode)
AMAZON_LWA_CLIENT_ID=your_client_id
AMAZON_LWA_CLIENT_SECRET=your_client_secret
AMAZON_LWA_REFRESH_TOKEN=your_refresh_token

# SP-API Configuration (optional)
AMAZON_SP_API_REGION=na  # na, eu, fe
AMAZON_MARKETPLACE_ID=ATVPDKIKX0DER  # US marketplace
```

### Safety

- If credentials are not set, the system runs in mock-only mode
- No live Amazon connection is made
- All operations are local/sandbox only

## API Endpoints

### GET `/api/v1/amazon/status`
Returns connection status including:
- `configured`: Whether credentials are available
- `sandbox`: Always True
- `environment`: Always "sandbox"
- `mode`: Always "read-only"

### GET `/api/v1/amazon/orders`
List orders from Amazon sandbox.

### POST `/api/v1/amazon/orders/import`
Import orders with idempotency.

### GET `/api/v1/amazon/info`
Returns integration information including:
- API version (v2026-01-01)
- Sandbox endpoints
- Rate limits
- Supported operations

## Order Flow

1. **Amazon Sandbox Order** → Retrieved via SP-API
2. **AmazonOrderProvider** → Normalizes to internal format
3. **Validation** → Validates order data
4. **PII Boundary** → Anonymizes buyer email
5. **Normalized Order** → Ready for internal processing
6. **Existing OrderService** → Creates internal order
7. **Address Processing** → Validates shipping address
8. **Inventory Check** → Checks inventory availability
9. **Inventory Reservation** → Reserves inventory
10. **Fulfillment Preparation** → Prepares supplier payload
11. **WAITING_APPROVAL** → **STOP** — No auto-submit

## Rate Limits

- Sandbox: 5 requests/second, burst 15
- Production: 1-5 requests/second, burst varies by operation

## Error Handling

- Authentication failures → Clear error message
- Rate limiting → Automatic retry with backoff
- Network errors → Recoverable, retry supported
- Invalid responses → Graceful handling
- Production endpoint access → Blocked with error

## Testing

All tests use mock data — no real Amazon credentials required:
- 70+ tests covering LWA authentication
- SP-API client behavior
- Order normalization
- Production endpoint blocking
- Read-only enforcement
- Credential protection
- Rate limiting
- Multi-tenant isolation

## Security

- Credentials never logged
- Tokens never exposed to frontend
- Production endpoints blocked
- Read-only operations enforced
- Approval gate remains authoritative
