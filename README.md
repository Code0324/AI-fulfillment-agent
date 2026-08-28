# Amazon AI Fulfillment Assistant

AI-powered order fulfillment workspace for Amazon sellers.

## Current Development Phase

**Chunk 1Y — Amazon Production Activation Gate** (see [docs/roadmap.md](docs/roadmap.md) for full chunk history)

The backend implements orders, inventory reservation, address processing, a
supplier fulfillment workflow with human-approval gating, a browser
automation sandbox, and a read-only Amazon SP-API integration layer — all
backed by in-memory storage (no database yet) and mock/sandbox providers.
User authentication is not implemented; the frontend login/register pages
are non-functional placeholders. See [docs/architecture.md](docs/architecture.md)
and the `docs/chunk-*-final-report.md` files for details on what exists.

## Technology Stack

| Layer    | Technology          |
| -------- | ------------------- |
| Frontend | Next.js, TypeScript, Tailwind CSS |
| Backend  | Python 3.12, FastAPI |

## Folder Structure

```
Amazon-AI-Fulfillment-Agent/
├── frontend/          # Next.js application
├── backend/
│   └── app/
│       ├── main.py    # FastAPI application entry point
│       └── core/      # Core modules (reserved for future use)
├── docs/
│   ├── architecture.md
│   └── roadmap.md
├── .env.example
├── .gitignore
└── README.md
```

## Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

The frontend runs at [http://localhost:3000](http://localhost:3000).

## Backend Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

The backend runs at [http://localhost:8000](http://localhost:8000).

## Health Endpoint

```
GET http://localhost:8000/health
```

Expected response:

```json
{
  "status": "ok"
}
```

## Current Limitations

- No database — all data (orders, inventory, workflows) is in-memory and reset on restart
- No user authentication — login/register pages are UI-only, not wired to a backend
- Amazon integration is read-only and requires real SP-API credentials to connect
  to Amazon's sandbox; without credentials the system runs in mock-only mode
  (see `docs/amazon-human-activation-checklist.md`)
- No real supplier/3PL integration — the supplier fulfillment flow is a
  synthetic sandbox for demonstrating the workflow and approval gate
- No payment functionality

## Future Roadmap

See [docs/roadmap.md](docs/roadmap.md) for the full development roadmap.
# AI-fulfillment-agent
