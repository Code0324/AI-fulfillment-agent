# Oracle Cloud Deployment Plan

Infrastructure/deployment plan for running this project on an Oracle Cloud
Infrastructure (OCI) Compute instance, **in addition to** (not instead of)
the existing Vercel frontend deployment. This is an infra-only change: no
business logic (orders, inventory, fulfillment, Amazon integration, address
processing, auth placeholders) is modified. The one code change made for
deployment is a CORS allow-list addition (see "Required code changes"),
which is necessary for the backend to accept requests from a non-localhost
origin at all.

## 1. Current architecture (as found)

| Layer | Technology | Notes |
|---|---|---|
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind | Client-side `fetch` calls to the backend via `NEXT_PUBLIC_API_BASE_URL` (baked in at build time, see `frontend/src/lib/api.ts`). Currently deployed on Vercel. |
| Backend | FastAPI (Python 3.12), single Uvicorn process | All routes under `/api/v1/*` plus a root `/health`. |
| Storage | **None — in-memory Python dicts** | `TaskService`, `OrderService`, `InventoryService`, fulfillment/automation/address services all hold state in process memory. Restarting the process wipes all data. |
| Background workers | **None** | No Celery/RQ/APScheduler, no `asyncio.create_task` fire-and-forget work, no queues. Everything runs synchronously inside the request/response cycle. |
| Browser automation | Mock only | `create_browser_session()` returns a `MockBrowserSession` in sandbox mode and explicitly raises in non-sandbox mode ("Production browser sessions are not yet implemented"). Playwright is **not** a dependency. Screenshots are plain `.txt` mock files written to a local `screenshots/` folder — ephemeral, not required to persist. |
| Auth | None | Login/register pages are UI placeholders; nothing to secure/rotate on the backend for auth. |
| Logging | `StreamHandler(sys.stdout)` | Already container-friendly; no file logging to worry about. |

**Implication for deployment:** because state is in-memory and unshared,
the backend **must run as exactly one instance/replica**. No load
balancing across multiple backend containers, no rolling/zero-downtime
restarts without losing all orders/inventory/workflow data. This is a
pre-existing limitation of the codebase, not something introduced by this
deployment — it's called out here because it directly constrains the
Compose/OCI topology (single backend container, `restart: unless-stopped`,
no replica count > 1).

## 2. Target architecture

```
                         Internet
                            │
                    OCI Compute Instance (Ubuntu, Docker)
                            │
                    ┌───────▼────────┐
                    │  Caddy (proxy)  │  :80 / :443 (public, TLS via Let's Encrypt)
                    └───┬────────┬────┘
          app.yourdomain.com   api.yourdomain.com
                    │                │
            ┌───────▼──────┐  ┌──────▼───────┐
            │  frontend     │  │  backend      │
            │  Next.js      │  │  FastAPI/     │
            │  :3000        │  │  Uvicorn      │
            │  (internal)   │  │  :8000        │
            └───────────────┘  │  (internal)   │
                                └───────────────┘

Vercel deployment: UNCHANGED, continues serving from its existing URL
independently of this stack (kept as fallback/staging per your instruction).
```

Two subdomains are used (rather than one host with path-based routing)
because the frontend already calls the backend via a single absolute
`NEXT_PUBLIC_API_BASE_URL` — a dedicated API subdomain requires zero
frontend code changes.

## 3. Environment variables

### Backend (`.env`, loaded by `docker compose` / `app.core.config.Settings`)

| Variable | Required | Default | Notes |
|---|---|---|---|
| `APP_ENV` | recommended | `development` | Set to `production` on OCI — switches logging to JSON format. |
| `BACKEND_HOST` | no | `0.0.0.0` | Already correct for containers. |
| `BACKEND_PORT` | no | `8000` | Internal container port. |
| `FRONTEND_PORT` | no | `3000` | Used only to build the localhost CORS defaults. |
| `ALLOWED_ORIGINS` | **yes, in production** | *(empty)* | **New.** Comma-separated extra CORS origins, e.g. `https://app.yourdomain.com,https://your-vercel-app.vercel.app`. Added in this change — see below. |
| `AMAZON_LWA_CLIENT_ID` / `AMAZON_LWA_CLIENT_SECRET` / `AMAZON_LWA_REFRESH_TOKEN` | no | empty | Unchanged. Leave unset to stay in mock-only mode. |
| `AMAZON_SP_API_REGION` | no | `na` | Unchanged. |
| `AMAZON_MARKETPLACE_ID` | no | `ATVPDKIKX0DER` | Unchanged. |
| `AMAZON_ENVIRONMENT` | no | `sandbox` | Unchanged; requires all 3 LWA vars to go to `production`. |

### Frontend (build-time, `NEXT_PUBLIC_*` vars are inlined into the JS bundle)

| Variable | Required | Notes |
|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | yes | For the OCI-hosted frontend, set to `https://api.yourdomain.com`. **Must be passed as a Docker build-arg**, not a runtime env var — Next.js inlines `NEXT_PUBLIC_*` values at `next build` time. |

### Compose/proxy-level

| Variable | Required | Notes |
|---|---|---|
| `FRONTEND_DOMAIN` | yes | e.g. `app.yourdomain.com` — used by Caddy for TLS + routing. |
| `API_DOMAIN` | yes | e.g. `api.yourdomain.com` — used by Caddy for TLS + routing. |

## 4. Ports

| Port | Exposed to | Purpose |
|---|---|---|
| 80, 443 | Public internet | Caddy — HTTP (redirects to HTTPS) and HTTPS. |
| 22 | Your IP only (recommended) | SSH admin access. |
| 3000 | Internal Docker network only | Next.js (`next start`), not published to the host. |
| 8000 | Internal Docker network only | Uvicorn/FastAPI, not published to the host. |

## 5. Database requirements

**None exist today, and none are added by this change.** The app has no
SQL/NoSQL dependency anywhere in `requirements.txt` or the service layer —
all persistence is in-memory. Wiring up a real database (e.g. PostgreSQL)
would require rewriting `TaskService`, `OrderService`, `InventoryService`,
the fulfillment workflow store, and the address-processing store to use a
DB session instead of a dict — a substantial change to business logic that
is explicitly **out of scope** for this deployment task.

Documented as follow-up work: when persistence is needed, add a
`postgres` service to `docker-compose.yml`, a `DATABASE_URL` env var, and
migrate the services above incrementally (e.g. behind a repository
interface) rather than as one large rewrite.

## 6. Redis / caching / queues

Not present in the codebase and not added here — there is nothing async,
scheduled, or queued to back with Redis. If a future feature needs a job
queue (e.g. real Playwright automation replacing the current mock), that's
the point to introduce Redis + a worker, not before.

## 7. Background workers

None exist (see §1) and none are introduced. The FastAPI process handles
everything synchronously per-request.

## 8. Production commands

| Component | Command | Notes |
|---|---|---|
| Backend | `uvicorn app.main:app --host 0.0.0.0 --port 8000` | **No `--reload`, no `--workers > 1`** (in-memory state must stay in one process). |
| Frontend | `npm run build` then `npm start` | `next start` binds `0.0.0.0` by default inside the container; respects `PORT` if set. |
| Full stack (OCI) | `docker compose up -d --build` | Builds and starts backend, frontend, and Caddy. |
| Health checks | `curl http://localhost:8000/health` (backend), `curl http://localhost:3000` (frontend), both via Compose healthchecks too | Used by Compose `healthcheck:` blocks and for manual verification. |

## 9. Required code changes (deployment-necessitated only)

1. **`backend/app/core/config.py`** — extend `CORS_ORIGINS` to also read a
   comma-separated `ALLOWED_ORIGINS` env var, in addition to the existing
   hardcoded localhost origins. Without this, the backend rejects every
   browser request from any non-localhost frontend (Vercel or the OCI
   frontend) with a CORS error — this is a hard blocker for the stated
   goal, not an optional cleanup.
2. No other backend or frontend source files change. `next.config.js` is
   left untouched specifically so the Vercel build pipeline sees no
   behavioral difference.

## 10. New deployment-only files (this change)

- `backend/Dockerfile`, `backend/.dockerignore`
- `frontend/Dockerfile`, `frontend/.dockerignore` (does **not** touch
  `next.config.js`; builds with plain `next build` / `next start`, not
  `output: "standalone"`, to guarantee zero effect on Vercel's own build)
- `docker-compose.yml` (repo root)
- `deploy/Caddyfile`
- `.env.example` additions (new vars only, existing ones untouched)

## 11. OCI provisioning steps

1. **Create the compute instance**: OCI Console → Compute → Instances →
   Create. Ubuntu 22.04/24.04 LTS image, shape sized for a small Next.js +
   FastAPI stack (an Ampere A1 flex shape with 2 OCPU / 12GB is comfortably
   within the Always Free tier and enough for this workload).
2. **Networking / firewall (NSG or Security List)**: open ingress
   - TCP 22 (SSH) — restrict to your IP if possible
   - TCP 80 and TCP 443 (HTTP/HTTPS) — open to `0.0.0.0/0`
   Do **not** open 3000 or 8000 publicly; they stay inside the Docker
   network behind Caddy.
   Also run `sudo ufw allow 22,80,443/tcp` (or configure `iptables`) on the
   instance itself — OCI's Ubuntu images ship with `iptables` rules that
   block traffic even when the NSG/Security List allows it.
3. **Install Docker**:
   ```bash
   curl -fsSL https://get.docker.com | sudo sh
   sudo usermod -aG docker $USER   # log out/in after this
   sudo apt-get install -y docker-compose-plugin
   ```
4. **Deploy the code**:
   ```bash
   git clone <your-repo-url>
   cd Amazon-AI-Fulfillment-Agent
   cp .env.example .env
   # edit .env: set APP_ENV=production, ALLOWED_ORIGINS, FRONTEND_DOMAIN,
   # API_DOMAIN, NEXT_PUBLIC_API_BASE_URL, and (optionally) Amazon creds
   docker compose up -d --build
   ```
5. **DNS**: point `app.yourdomain.com` and `api.yourdomain.com` A records
   at the instance's public IP. Caddy automatically provisions and renews
   Let's Encrypt certificates for both once DNS resolves.
6. **Verify**:
   ```bash
   curl -I https://api.yourdomain.com/health
   curl -I https://app.yourdomain.com
   ```

## 12. Keeping Vercel intact

- No file under Vercel's build scope (`frontend/next.config.js`,
  `frontend/vercel.json` if any, `package.json` scripts) is modified.
- The only thing you may want to do on the Vercel side — entirely outside
  this repo change, at your discretion — is set `NEXT_PUBLIC_API_BASE_URL`
  in the Vercel project's environment variables to point at
  `https://api.yourdomain.com` if you want the Vercel deployment to talk to
  the new OCI backend instead of (or in addition to, via a separate
  preview env) `http://127.0.0.1:8000`. That is a dashboard configuration
  change on Vercel's side, not a code change, and is left to you.
- If you do that, add the Vercel deployment's URL to `ALLOWED_ORIGINS` on
  the OCI backend so CORS allows it.
