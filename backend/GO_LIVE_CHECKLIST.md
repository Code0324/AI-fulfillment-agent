# Go-Live Checklist

Everything in this app currently runs in mock/sandbox mode by default. This
file lists every remaining credential/API-key/config item needed to move
each integration from mock to production, plus the operational actions
that go with them. It is meant to be the **only** remaining to-do list —
if you find anything structurally unfinished that isn't just "add a
credential," that's a bug, not a checklist item; open an issue instead of
adding a line here.

Each item names the exact env var(s) it fills (see `.env.example` for the
full annotated list) and where to get the value.

---

## 1. TikTok Shop OAuth app approval

| Env var | Where to get it |
|---|---|
| `TIKTOK_APP_KEY` | [TikTok Shop Partner Center](https://partner.tiktokshop.com) → create/register an app |
| `TIKTOK_APP_SECRET` | Same app registration page |
| `TIKTOK_ACCESS_TOKEN` | Generated via the app's OAuth authorization flow once a real shop authorizes it |
| `TIKTOK_REFRESH_TOKEN` | Same OAuth flow — used to refresh the access token (see `app/services/providers/tiktok/auth.py`) |
| `TIKTOK_SHOP_ID` | The authorized shop's ID, shown in Partner Center / Seller Center after authorization |
| `TIKTOK_ENVIRONMENT` | Set to `production` once the above are real (defaults to `sandbox`) |

**Before setting these in production**, read
`docs/tiktok-integration.md` — it documents, endpoint by endpoint, which
parts of `app/services/providers/tiktok/api_client.py` (path segments,
pagination parameter names, the fulfillment-update endpoint path, rate
limits) were corroborated against TikTok's own docs vs. left as
conservative, **unverified placeholders** pending an approved developer
app's access to the interactive docs. Re-verify those specifically once
you have real API access — the client fails loudly on an unexpected
response shape rather than fabricating data, but an unverified endpoint
path can still 404 until confirmed.

## 2. Google Sheets service account

Two independent integrations, each needing its own credential:

| Purpose | Env var(s) | Where to get it |
|---|---|---|
| App's own TikTok-order sync (`app/services/google_sheets/client.py`) — one fixed spreadsheet/worksheet | `GOOGLE_SHEETS_SPREADSHEET_ID`, `GOOGLE_SHEETS_CREDENTIALS_JSON`, `GOOGLE_SHEETS_WORKSHEET_NAME` | [Google Cloud Console](https://console.cloud.google.com) → create a service account → enable the Sheets API → create a JSON key → paste its contents (as a single-line JSON string) into `GOOGLE_SHEETS_CREDENTIALS_JSON`. Then share the target spreadsheet with the service account's `...@...iam.gserviceaccount.com` email (Editor access). |
| Generic Google Sheets MCP server (`backend/mcp_servers/google_sheets/`) — arbitrary sheet/range per call | `GOOGLE_SHEETS_CREDENTIALS_PATH` | Same service account (or a separate one) — this variant wants the JSON key as a **file path** on disk, not a JSON string. Share whichever spreadsheets you want it to touch with the same service account email. |

## 3. Amazon SP-API production access

| Env var | Where to get it |
|---|---|
| `AMAZON_LWA_CLIENT_ID` | [Amazon Seller Central](https://sellercentral.amazon.com) → Develop Apps → register an SP-API app |
| `AMAZON_LWA_CLIENT_SECRET` | Same app registration |
| `AMAZON_LWA_REFRESH_TOKEN` | Generated via the app's LWA authorization flow once a real seller account authorizes it |
| `AMAZON_SP_API_REGION` | `na` / `eu` / `fe` — pick based on your marketplace |
| `AMAZON_MARKETPLACE_ID` | Your Amazon marketplace ID (defaults to US: `ATVPDKIKX0DER`) |
| `AMAZON_ENVIRONMENT` | Set to `production` once the above are real (defaults to `sandbox`; `app/core/config.py` refuses to report `production` unless credentials are actually present) |

Follow `docs/amazon-human-activation-checklist.md` for the full
step-by-step activation process. Remember: this integration is
**Orders-API-only and read-only** by design (see
`app/services/providers/amazon/sp_api_client.py`) — there is no path to
making it place or modify orders, and none should be added without a
matching update to the safety-gate/approval logic in
`app/services/fulfillment/workflow.py`.

## 4. Amazon pricing provider — choice + credentials

`PRICING_PROVIDER` defaults to `mock` (synthetic data — **not** a real
price feed). Before go-live, deliberately choose one:

| `PRICING_PROVIDER` | Extra env var(s) needed | Where to get it |
|---|---|---|
| `pa_api` (recommended if eligible) | `AMAZON_PA_API_ENABLED=true`, `AMAZON_PA_API_ACCESS_KEY`, `AMAZON_PA_API_SECRET_KEY`, `AMAZON_PA_API_PARTNER_TAG` | [Amazon Associates](https://associates.amazon.com) → **requires an already-approved Associates/affiliate account** with PA-API access enabled. Amazon can revoke PA-API access for accounts that don't generate qualifying sales volume — this is a real, ongoing eligibility requirement, not a one-time signup. |
| `scrape` (last resort only) | `AMAZON_SCRAPE_PRICING_ENABLED=true` | No credentials — but read `app/services/providers/amazon/scrape_pricing.py`'s module docstring first. This is fragile (Amazon's page markup changes without notice) and a real Terms-of-Service exposure (Amazon's Conditions of Use prohibit automated scraping of the retail site outside licensed APIs). **Never live-tested against the real site in this repo** — only its HTML-parsing logic was verified, against static fixtures. |
| `mock` | none | Stays mock. Fine for staging; **do not use in production** — the price safety-gate (`services/fulfillment/workflow.py`'s `check_price_guard` step) will pass every order based on fake prices if this is still `mock` at go-live. |

Also review `MAX_ALLOWED_PRICE_USD` (defaults to `500.00`, an arbitrary
placeholder) — set it to whatever your actual maximum-auto-proceed price
should be before go-live.

Amazon-sourced orders now carry a real ASIN via `Order.asin` (a
first-class, nullable column — `app/models.py`; the `check_price_guard`
step uses it directly, before falling back to TikTok's SKU-mapping
resolution). Nothing in this codebase's Amazon-order ingestion path sets
it automatically yet — pass it explicitly (e.g. via the `amazon` MCP
server's `create_order(..., asin=...)`) wherever you have it, or the price
gate will correctly-but-harmlessly report "not applicable" and let the
order proceed unchecked, same as any order with no knowable ASIN.

## 5. Notification provider — choice + credentials

`NOTIFICATION_PROVIDER` defaults to `log` (writes to the application log
only — never reaches a human). Before go-live, choose a real channel if
you want orders in `WAITING_APPROVAL`/`FAILED` to actually page someone
(see `backend/mcp_servers/notifications/`):

| `NOTIFICATION_PROVIDER` | Extra env var(s) needed | Where to get it |
|---|---|---|
| `slack` | `SLACK_WEBHOOK_URL` | [Slack Incoming Webhooks](https://api.slack.com/messaging/webhooks) → create one for the channel you want alerts in. Treat the URL as a credential. **Never live-tested against a real Slack workspace in this repo** (no webhook URL available) — the request-building logic is verified, the real POST is not. |
| `log` | none | Stays log-only. Fine for staging; **not sufficient for production** — nobody is paged. |

**Known limitation, not fixed by credentials alone:** `list_pending_reviews`/
`notify_workflow_needs_review` only see workflow state held in their own
process's memory — `fulfillment_engine` isn't DB-backed (see
`mcp_servers/notifications/server.py`'s module docstring for the full
explanation). When the orchestrator spawns `notifications` as its own
subprocess, it won't see orders created via the separately-spawned
`amazon` server. `notify()` itself is unaffected. This is a real,
pre-existing architectural characteristic of the fulfillment engine —
closing it means making that engine DB-backed, which is outside this
task's scope.

## 6. Test suite against a real database — verified live

```bash
./scripts/run_tests_with_db.sh
```

**Actually run against a real, disposable PostgreSQL instance (not just
statically verified) — 920 passed, 3 failed, 0 errors.** The 3 failures
are pre-existing and unrelated to this work (`asyncio.get_event_loop()`
deprecation on Python 3.12 in `test_production_readiness.py`'s SP-API
client tests — a file untouched by any of this work). This run included
every `create_order`/approval-gate test, every price-safety-gate test
(direct-ASIN, SKU-mapping-fallback, and not-applicable paths), and the
notification-provider tests. Re-run this after any future change that
touches the fulfillment workflow, providers, or migrations — it only
takes Docker.

## 7. Also worth reviewing (not credentials, but easy to forget)

- `SECRET_KEY` — defaults to `"default-dev-secret-change-in-production"`
  in `app/core/config.py`. Generate a real random secret for production.
- `DATABASE_URL` — point at your real production PostgreSQL instance, not
  the local-dev default.
- `ALLOWED_ORIGINS` / `FRONTEND_DOMAIN` / `API_DOMAIN` — see
  `.env.example`'s "Oracle Cloud / Docker Compose deployment only"
  section, needed for a real deployed frontend/domain.
