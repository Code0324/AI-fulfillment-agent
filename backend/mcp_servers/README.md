# MCP servers

Real [Model Context Protocol](https://modelcontextprotocol.io) servers (official
Python SDK, package `mcp`) for this app, living alongside — not replacing — the
existing plain-Python provider architecture in `app/services/providers/`. Every
tool below is a thin wrapper over code that already exists in this repo (a
provider, the fulfillment workflow engine, inventory/order services); none of
them reimplement SP-API, TikTok Shop API, Google Sheets, or browser-automation
logic.

```
backend/mcp_servers/
  amazon/            # wraps app.services.providers.amazon + the fulfillment workflow
  tiktok_shop/        # wraps app.services.providers.tiktok.TikTokOrderProvider
  google_sheets/       # generic Sheets API v4 client (reporting/export only)
  notifications/        # alerts a human when a workflow needs review (log/Slack)
  orchestrator/           # "Multi-Client MCP" — connects to the four above as
                           # a client and re-exposes them as one MCP server
```

## Running a server standalone

Each server speaks MCP over stdio and can be run directly from `backend/`:

```bash
cd backend
python -m mcp_servers.amazon.server
python -m mcp_servers.tiktok_shop.server
python -m mcp_servers.google_sheets.server
python -m mcp_servers.orchestrator.server
```

Each expects to be launched with `backend/` as the working directory (so
`app` and `mcp_servers` are both importable) — see each server's entry in
`orchestrator/mcp_servers.json` for the exact command/args used when the
orchestrator launches them itself.

## amazon

Wraps `app.services.providers.amazon.order_provider.AmazonOrderProvider`
(the existing read-only SP-API Orders API sandbox integration),
`app.services.providers.pricing_base.PricingProviderBase` (price/inventory/
product-detail lookups — see "Pricing providers" below), and
`app.services.fulfillment.workflow.fulfillment_engine` (the existing
approval-gated fulfillment workflow).

| Tool | Behavior |
|---|---|
| `get_product(asin)` | Product details (title) via the active pricing provider. SP-API itself has no Catalog Items API in this codebase; not called for this. |
| `check_price(asin)` | Current price via the active pricing provider. SP-API itself has no Pricing API in this codebase; not called for this. |
| `check_inventory(asin)` | Two distinct sources, both returned: `internal` (our own stock — resolves the ASIN to a SKU via a confirmed `sku_mappings` row, then reads `inventory_service`) and `amazon` (Amazon's own listing availability, via the active pricing provider). |
| `get_order_status(order_id)` | Wraps `AmazonOrderProvider.get_order` (read-only SP-API). |
| `get_tracking(order_id)` | Same provider call — reports honestly that package/tracking data isn't parsed out of the SP-API response by this codebase's normalizer. |
| `create_order(sku, quantity, shipping_address, customer_name, product_name, organization_id)` | Creates an order via `order_service` and starts `fulfillment_engine`'s existing approval-gated workflow. **Never executes a supplier submission directly** — returns `status="pending_approval"` whenever the workflow reaches `WAITING_APPROVAL`. Approving/rejecting a pending order is unchanged and still goes through the existing `/api/v1/fulfillment` endpoints — no new approval mechanism was added. |

`organization_id`/`customer_name`/`product_name` are required even though a
minimal `(sku, qty, shipping_address)` signature might suggest otherwise:
order creation in this codebase is always tenant-scoped (no default
organization) and `customer_name`/`product_name` are required, non-empty
fields on the underlying order.

### Pricing providers (`app/services/providers/pricing_base.py`)

Exactly one is active process-wide, selected via `PRICING_PROVIDER`
(`app/core/config.py`, wired through `app/services/providers/registry.py`).
Every implementation either returns real data or raises
`PricingProviderError` — never a fabricated price.

| Provider | `PRICING_PROVIDER` | Real data source | Trade-off |
|---|---|---|---|
| `MockPricingProvider` | `mock` (**default**) | Deterministic synthetic data, hash-derived per ASIN | Always "works"; not real. Safe default for dev/test. |
| `PAAPIPricingProvider` | `pa_api` | Amazon Product Advertising API v5 (`amazon/pa_api_pricing.py`) | Real live data, but requires an **approved Amazon Associates account** — eligibility can be revoked for low sales volume. Never live-tested in this repo (no credentials available). |
| `ScrapePricingProvider` | `scrape` | Parses `amazon.com/dp/{asin}` HTML (`amazon/scrape_pricing.py`) | No credentials needed, but fragile (markup changes silently) and ToS-sensitive (Amazon prohibits automated scraping of the retail site) — **last resort only**, never the recommended default. |

`app.services.fulfillment.workflow`'s price safety-gate step
(`check_price_guard`, runs right after SKU-mapping resolution) calls
`get_price()` through this same abstraction before an order can reach
human approval: if the price can't be determined (provider not configured,
request failed) or exceeds `MAX_ALLOWED_PRICE_USD`, the workflow **stops**
(`FAILED`, with a clear reason) rather than proceeding — never silently
skipped, never auto-approved. See that method's docstring for exactly how
an ASIN is resolved per order source (TikTok-sourced orders reuse the ASIN
already resolved by SKU-mapping; orders with no resolvable ASIN — this
includes all `MANUAL` orders and, currently, direct Amazon-sourced orders
too, since this codebase has no first-class ASIN field on `Order` yet —
report the check as "not applicable" and proceed normally).

## tiktok_shop

A TikTok Shop provider already existed at
`app.services.providers.tiktok.order_provider.TikTokOrderProvider` with
exactly the four methods this server needs — this server wraps it as-is.

| Tool | Behavior |
|---|---|
| `get_orders()` | List TikTok Shop orders. |
| `get_order_details(order_id)` | Full order detail. |
| `get_order_status(order_id)` | Raw status string. |
| `update_fulfillment(order_id, tracking_number, shipping_provider_id)` | Confirms shipment — a real write. |

**Mock mode:** set `TIKTOK_MOCK_MODE=true` to make every tool above return
small, clearly-labeled (`"mock": true`) synthetic fixture data defined
directly in `tiktok_shop/server.py`, without touching
`TikTokOrderProvider` or requiring real credentials.
`app.services.providers.tiktok.__init__` documents, by explicit design,
that there is no `MockTikTokProvider` anywhere in the provider tree (the
real provider fails loudly — `ProviderUnavailableError` — rather than
silently returning empty data when unauthorized, so a caller can never
mistake "not configured" for "zero real orders"). Mock mode here respects
that boundary: it lives at the MCP layer only. Default (`TIKTOK_MOCK_MODE`
unset) calls the real provider, which raises `ProviderUnavailableError`
when TikTok Shop credentials aren't configured — the same as every other
caller of that provider in this app.

## google_sheets

**PostgreSQL is the source of truth for this application.** This server is a
reporting/operations view layer only — read/write here is export/sync for
human visibility and is never fed back into this app's own order/inventory/
fulfillment state.

Uses the Google Sheets API v4 directly (`google-api-python-client` +
`google-auth`) with a service account key **file**, path from
`GOOGLE_SHEETS_CREDENTIALS_PATH`. This is intentionally separate from
`app/services/google_sheets/client.py`, the app's existing narrow,
single-spreadsheet TikTok-order sync path (which reads its service account
key as a JSON string from `GOOGLE_SHEETS_CREDENTIALS_JSON`) — that module is
unmodified. The MCP tools below need to operate on whatever `sheet_id`/range
an agent supplies, not one fixed spreadsheet+worksheet.

| Tool | Behavior |
|---|---|
| `read_rows(sheet_id, range)` | Read an A1 range, e.g. `"Sheet1!A1:O50"`. |
| `append_row(sheet_id, values)` | Append one row to the sheet's default tab. |
| `update_row(sheet_id, row_id, values)` | Overwrite one 1-indexed row starting at column A. |
| `find_row(sheet_id, query)` | Linear-scan the default tab for the first row containing `query` in any cell. |

## notifications

Closes a real, pre-existing gap: `docs/architecture.md` has listed a
"Notification System — Alerts and status updates" as a planned-but-never-
built layer since this project's earliest architecture doc, and nothing in
this codebase pages a human when a fulfillment workflow needs review.
Every order that stops at `WAITING_APPROVAL` (the existing human-approval
gate) or `FAILED` (e.g. the price safety-gate — see `amazon`'s
`create_order` above) currently just sits there until someone happens to
check the dashboard; `WAITING_APPROVAL` even auto-expires after one hour
if nobody acts. This server does not modify the fulfillment workflow
engine — it only reads real state from it and calls out through
`app.services.providers.notifications_base` (selected via
`NOTIFICATION_PROVIDER`).

| Tool | Behavior |
|---|---|
| `notify(title, message, severity)` | Send a notification through the active provider. `severity` is `info`/`warning`/`critical`. |
| `list_pending_reviews()` | Read-only: list every workflow currently `WAITING_APPROVAL` or `FAILED`. |
| `notify_workflow_needs_review(workflow_id)` | Send an alert built from a real workflow's current state — refuses if that workflow isn't actually in a review-needed status, so this can't be used to dress up an arbitrary message as a workflow alert. |

Providers (`NOTIFICATION_PROVIDER`, default `log`):

| Provider | Real channel | Trade-off |
|---|---|---|
| `LogNotificationProvider` (`log`, **default**) | Writes a real log line | Always works, never fails — but doesn't reach a human. Safe default so real alerting is a deliberate choice, same reasoning as `PRICING_PROVIDER`. |
| `SlackWebhookNotificationProvider` (`slack`) | Posts to a Slack incoming-webhook URL (`SLACK_WEBHOOK_URL`) | Real, simple (no OAuth) — but never live-tested in this repo (no webhook URL available). |

**Known limitation — read before relying on `list_pending_reviews`/
`notify_workflow_needs_review` through the orchestrator:** `fulfillment_engine`'s
workflow state is held purely in an in-memory dict, per Python process — not
persisted to the `fulfillment_workflows` table that exists in `app/models.py`
(that table is defined but never read or written anywhere in this codebase).
When the orchestrator spawns this server as its own subprocess, it cannot
see workflows created via the separately-spawned `amazon` server's
subprocess. `notify()` is unaffected. This is a pre-existing architectural
characteristic of the fulfillment engine, not something fixable within this
server's scope — see `mcp_servers/notifications/server.py`'s module
docstring.

## orchestrator ("Multi-Client MCP")

An MCP *client* that connects to the four servers above over stdio at
startup, aggregates their tool lists, and re-exposes them as a single MCP
*server* — an AI agent can call any tool without knowing which underlying
server owns it.

- `config.py` loads the child-server list from `mcp_servers.json` (stdio
  command/args per server), so servers can be added or removed without
  touching code. Override the file with `MCP_ORCHESTRATOR_CONFIG`.
- `client_manager.py` (`MultiClientManager`) connects to every configured
  server, discovers its tools, and routes a call to the right one. Because
  `amazon` and `tiktok_shop` both define a tool named `get_order_status`,
  every tool is exposed **namespaced** as `"{server_name}__{tool_name}"`
  (e.g. `amazon__get_order_status`, `tiktok_shop__get_order_status`) —
  never bare names, so there's no ambiguity for either server.
- `permissions.py` classifies tools as safe (read-only — `get_*`, `check_*`,
  `read_*`, `list_*`, `find_*`) vs. requiring confirmation (`create_order`,
  `update_fulfillment`, `append_row`, `update_row`, `notify`,
  `notify_workflow_needs_review`, and any unrecognized tool name,
  safe-by-default). A write tool call must include `"confirmed": true` in
  its arguments or the orchestrator refuses it with an explanation — this
  is a call-time safety prompt, **not** a second approval queue.
  `create_order`'s real, authoritative approval gate is still
  `fulfillment_engine`'s existing `WAITING_APPROVAL` workflow (see the
  `amazon` server above) — confirmation here only stops an agent from
  firing off a mutating call it didn't mean to make.
- `server.py` is the orchestrator's own MCP server (built on the SDK's
  low-level `Server`, since its tool list is discovered dynamically at
  connect time rather than known at import time like the four leaf
  servers). Run it directly (`python -m mcp_servers.orchestrator.server`)
  to get one stdio MCP endpoint that fans out to all four.

## Registering with an MCP-compatible client

See the top-level `.mcp.json` in the repo root — it registers all five
servers (the four leaf servers individually, plus the orchestrator) so an
MCP-compatible client (Claude Code, Claude Desktop, ...) can connect to any
of them for testing. Environment variables each server needs are listed in
`.env.example`.

## Running the test suite against a real database (pre-go-live checklist item)

Most of this repo's tests — including every `create_order`/approval-gate
test for the `amazon` MCP server, and every price-safety-gate test in
`tests/test_price_safety_gate.py` — need a real PostgreSQL instance:
`order_service`/`fulfillment_engine` are backed by real persistence, not an
in-memory fake. A sandbox with no database available will show these
tests erroring with a connection failure, not a test failure — that is a
missing dependency, not a bug, and it's easy to mistake for one.

```bash
./scripts/run_tests_with_db.sh
```

This starts a disposable, throwaway PostgreSQL container (its own name,
port, and container lifecycle — never the docker-compose.yml `postgres`
service or its persistent volume; see the script's header comment for why
that separation matters — several tests issue real `DELETE FROM ...`
calls, which would be destructive against a real dev database), runs
`alembic upgrade head` against it, runs the full `pytest` suite, and tears
the container down on exit. Requires Docker. Pass extra arguments straight
through to `pytest`, e.g.:

```bash
./scripts/run_tests_with_db.sh tests/test_price_safety_gate.py -v
```

**This must be run, and confirmed passing, before go-live** — see
`backend/GO_LIVE_CHECKLIST.md`.
