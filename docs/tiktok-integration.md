# TikTok Shop Integration

Real production order-source integration for TikTok Shop, alongside the
existing Amazon SP-API integration. There is no mock TikTok provider
anywhere in this codebase — see `backend/app/services/providers/tiktok/`.

## What is implemented now

- A real (non-mock) `TikTokOrderProvider` (`services/providers/tiktok/order_provider.py`)
  implementing `get_orders()`, `get_order_details()`, `get_order_status()`,
  `update_fulfillment()`.
- `TikTokTokenManager` (`services/providers/tiktok/auth.py`) — in-memory
  token cache, refresh mechanics, and TikTok Shop's HMAC-SHA256
  request-signing shape.
- `TikTokAPIClient` (`services/providers/tiktok/api_client.py`) — sandbox/
  production gating, rate limiting, retry/backoff, order search/detail and
  fulfillment-update calls.
- `TikTokOrder` schema (`schemas/tiktok.py`) preserving the full real
  business field structure (Order ID, Date, SKU, Product Name, Variation,
  Qty, Recipient, Phone no, Address 1, Delivery instructions, City,
  State, Zipcode, Price, Delivery Date), not the simplified field set
  documented in `docs/amazon-data-requirements.md`.
- SKU + variation mapping engine (`services/sku_mapping/`) — deterministic
  exact matching, fuzzy suggestion (never auto-trusted), conflict
  detection, and explicit human-confirmed mapping.
- Fulfillment-workflow safety wiring (`services/fulfillment/workflow.py`,
  step 2 — `_step_check_inventory`): a TikTok order's SKU+variation is
  resolved before inventory reservation; anything not `MATCHED` (needs
  review, not found, or conflicting) stops the workflow with a reason,
  the same way address-validation uncertainty already does.
- Read-only status endpoints: `GET /api/v1/tiktok/status`, `GET /api/v1/tiktok/test-connection`.
- A DB-level idempotency guarantee: `UniqueConstraint(organization_id, tiktok_order_id)`
  on `fulfillment_orders`.

## What requires TikTok Shop developer credentials

Everything that makes a real API call: `get_orders()`, `get_order_details()`,
`get_order_status()`, `update_fulfillment()`, and the underlying token
refresh. Without credentials, `TikTokOrderProvider.is_configured` is
`False`, the provider is not registered into `provider_registry`, and
every public method on a directly-instantiated provider raises
`ProviderUnavailableError` rather than returning empty/fabricated data.

## What requires TikTok app approval

The same real-API surface above requires an approved TikTok Shop
Partner Center developer app with Order and Fulfillment API scopes
granted, in addition to credentials being present.

## Required environment variables

```
TIKTOK_APP_KEY=
TIKTOK_APP_SECRET=
TIKTOK_ACCESS_TOKEN=       # optional — avoids one refresh call on first use
TIKTOK_REFRESH_TOKEN=
TIKTOK_SHOP_ID=
TIKTOK_ENVIRONMENT=sandbox # or production
SKU_MAPPING_CONFIDENCE_THRESHOLD=0.90  # optional, suggestion floor — see below
```

`.env` is gitignored; `.env.example` should only ever carry placeholder
values — same rule as the existing `AMAZON_*` variables.

## OAuth flow (as implemented — see verification status below)

An authorized app exchanges a refresh token for a short-lived access
token via a signed request to TikTok's token-refresh endpoint
(`app_key`/`app_secret`/`refresh_token`/`grant_type=refresh_token`).
Tokens are cached in memory only, refreshed 5 minutes before expiry.

**Documentation verification status** (see the implementation plan this
was built from for the full record and sources):
- Corroborated against TikTok's own developer docs: the OAuth
  exchange/refresh parameter shape, and the general request-signing shape
  (HMAC-SHA256 over path + sorted query params + body, keyed by
  `app_secret`, passed as a `sign` query parameter).
- **Not verified this session** (TikTok's Partner Center docs are a
  JS-rendered SPA; automated fetch only returned the page shell): the
  exact token endpoint path, the byte-exact signing algorithm (whether
  `access_token`/`app_key`/`timestamp` are included in the signed string
  and their ordering), exact order-search/order-detail/fulfillment-update
  parameter names, pagination field names, batch limits, rate limits, and
  the error-response shape.
- Every unverified value in the code is a named constant with an explicit
  comment marking it as such — **re-verify against partner.tiktokshop.com
  (or the interactive docs available once a developer app is approved)
  before any of this is used against TikTok's real API.**

## API endpoints actually used

- `GET /order/202309/orders/search` — order search (pagination fields UNVERIFIED)
- `GET /order/202309/orders` — batch order detail (UNVERIFIED param name/batch limit)
- `POST /fulfillment/202309/packages/{package_id}/ship` — fulfillment update (path UNVERIFIED)
- Base domain: `open-api.tiktokglobalshop.com`

## SKU / variation mapping rules

1. **Deterministic exact match**: an exact `(organization_id, tiktok_sku, variation)`
   row in `sku_mappings` is returned as-is. This is the only path that
   can ever produce `status="matched"`.
2. **Fuzzy suggestion, never auto-trusted**: if no exact row exists, the
   engine compares against the corpus of already-explicitly-confirmed
   mappings for the same org (stdlib `difflib`). Regardless of score,
   this **never** returns `status="matched"` — it returns `needs_review`
   (with the best guess surfaced, not applied), `conflict` (two or more
   equally-plausible candidates), or `not_found` (nothing above the
   suggestion floor).
3. **Explicit confirmation**: `create_explicit_mapping()` is the only
   function that can write `status="matched"`. There is currently no
   HTTP endpoint or UI for this — see "Operational gap" below.
4. `SKU_MAPPING_CONFIDENCE_THRESHOLD` (default `0.90`) is a **suggestion
   floor**, not an auto-accept threshold.

## Failure states

| State | Effect |
|---|---|
| Not configured | Provider not registered; `/api/v1/tiktok/status` reports `configured: false`; direct method calls raise `ProviderUnavailableError` |
| Auth failure | `TikTokAuthenticationError`, `recoverable` flag set appropriately |
| API error | `TikTokAPIError`, mapped from HTTP status / TikTok's `code` envelope |
| SKU needs review / not found / conflict | Fulfillment workflow fails at step 2 with a reason; inventory is never reserved; fix via `create_explicit_mapping()` then `retry_workflow()` |

## Production activation steps

1. Obtain an approved TikTok Shop Partner Center developer app with
   Order + Fulfillment scopes.
2. **Re-verify** every item marked UNVERIFIED above against the live
   Partner Center docs (now accessible with the approved app) — do not
   go live on the placeholder constants in `api_client.py`/`auth.py`
   without this step.
3. Set `TIKTOK_*` environment variables; leave `TIKTOK_ENVIRONMENT=sandbox`
   until the above verification is complete, then switch to `production`.
4. Confirm `GET /api/v1/tiktok/test-connection` succeeds against the real
   API before relying on it.

## Production blockers (explicit, not implemented in this task)

1. Exact TikTok order-search/order-detail/fulfillment-update parameter
   names and response shape — see verification status above.
2. Byte-exact request-signing algorithm — general shape only.
3. A real order-ingestion pipeline that turns fetched `TikTokOrder`s into
   `FulfillmentOrder` rows — the DB-level idempotency constraint exists
   (`UniqueConstraint(organization_id, tiktok_order_id)`) but nothing
   writes through it yet. `TikTokOrderProvider.import_orders()`'s
   in-memory `_imported_order_ids` set is **dev/test bookkeeping only**
   and must not be cited as production-grade duplicate-order protection.
4. TikTok's webhook/Events push-notification receiver — not built;
   `get_orders()` polling is the only mechanism implemented.
5. Per-tenant credential storage/encryption. The existing `AmazonAccount`
   model in `models.py` is a dormant scaffold — nothing in the codebase
   reads or writes it, and there is no encryption utility in
   `core/security.py` despite its docstring. TikTok's credentials follow
   the pattern Amazon *actually* runs on today: single-tenant, env-var
   sourced. `TikTokTokenManager`'s constructor takes plain credential
   arguments specifically so a future per-tenant model can supply them
   without rewriting `auth.py`.
6. No confirmation UI/endpoint for `needs_review`/`conflict` SKU
   mappings — `create_explicit_mapping()` is a callable service function
   only; resolving a pending mapping today requires direct service/DB
   access.

## Real vs. test-only components

- **Real API client code**: `services/providers/tiktok/{auth,api_client,order_provider}.py`
  — no mock provider, no fabricated responses. Every response-parsing
  path raises rather than guessing.
- **Test fixtures**: `backend/tests/test_tiktok_provider.py` uses
  `unittest.mock.patch` on the HTTP layer with hand-built fixture
  payloads, explicitly named/commented as fixtures. These prove the
  code's logic is correct against a *given* response shape — they are
  **not** proof that a real TikTok API call succeeds, since the exact
  response shape itself is unverified (see above).
- **Unconfigured state**: no `TIKTOK_*` env vars set — provider not
  registered, every method raises `ProviderUnavailableError`.
- **Live validation blocked until credentials/app approval**: anything
  that would require an actual network round-trip to TikTok's real API.

## Also verified during this work (Amazon)

While auditing conventions to follow for TikTok, the existing Amazon
SP-API client's `API Version: Orders API v2026-01-01` header comment was
found to not match Amazon's real SP-API versioning convention (Amazon's
actual Orders API is versioned `v0`), and no test in this codebase
exercises a real or recorded HTTP request/response cycle against it —
every Amazon integration test mocks config/environment or calls
`_normalize_order` with a static dict. This is a pre-existing condition,
not something this task changed (the Amazon provider was explicitly not
modified), but is recorded here since it's directly relevant to trusting
"real API" claims in this codebase.
