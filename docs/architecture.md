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

## Current State (Chunk 1A)

- **Frontend**: A minimal Next.js application serving a landing/dashboard placeholder.
- **Backend**: A minimal FastAPI application exposing a `/health` endpoint.
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
