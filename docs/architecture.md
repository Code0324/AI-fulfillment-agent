# Architecture

## Overview

The Amazon AI Fulfillment Assistant follows a decoupled frontend-backend architecture.

```
Frontend (Next.js)
        │
        ▼
FastAPI Backend (Python)
        │
        ▼
Future Services (Database, AI, Browser Automation, Amazon API, etc.)
```

## Current State (Chunk 1Y)

- **Frontend**: A Next.js application with a marketing/landing site and a
  dashboard shell (orders, inventory, addresses, fulfillment, automation,
  analytics, settings). Login/register pages exist but are not wired to any
  backend authentication — there is none.
- **Backend**: A FastAPI application with routers for health, status, tasks,
  orders, inventory, automation, address processing, fulfillment workflow,
  providers, mock Amazon import, and (read-only) Amazon SP-API integration.
  All state is held in-memory (no database) — process restarts reset all data.
- **Fulfillment workflow**: Orchestrates order → address validation →
  inventory reservation → supplier sandbox → human approval → mock supplier
  submission → confirmation, with idempotency, per-order locking, audit
  logging, and approval expiry.
- **Amazon integration**: A provider abstraction (`app/services/providers/`)
  supports mock providers (always on) and a real Amazon SP-API read-only
  provider that activates only when LWA credentials are configured via
  environment variables; production endpoints are blocked unless
  `AMAZON_ENVIRONMENT=production` is explicitly set. See
  `docs/amazon-provider-contract.md` and `docs/amazon-human-activation-checklist.md`.
- **Communication**: The frontend and backend communicate over HTTP (CORS enabled for localhost:3000 → localhost:8000).

## Future Layers

Additional services will be introduced in later chunks:

- **Database** — Persistent storage for orders, suppliers, and configuration.
- **AI Agents** — Address parsing, order processing automation.
- **Browser Automation** — Amazon Seller Central interaction.
- **Supplier/3PL Integration** — Fulfillment partner APIs.
- **Notification System** — Alerts and status updates.

## Design Principles

1. Separation of concerns between frontend and backend.
2. Backend remains the single source of truth for business logic.
3. New services are added behind the backend — the frontend never calls external services directly.
4. Clean, extensible structure that supports incremental feature delivery.
