# Amazon AI Fulfillment Assistant

AI-powered order fulfillment workspace for Amazon sellers.

## Current Development Phase

**Chunk 1A — Project Foundation**

This is the initial project setup. Only the basic structure, frontend shell, and backend health endpoint exist. No business features have been implemented yet.

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

- No database connection
- No Amazon API integration
- No AI agents
- No browser automation
- No authentication
- No order processing
- No supplier/3PL integration
- No payment functionality

This is intentional — Chunk 1A only creates the project foundation.

## Future Roadmap

See [docs/roadmap.md](docs/roadmap.md) for the full development roadmap.
