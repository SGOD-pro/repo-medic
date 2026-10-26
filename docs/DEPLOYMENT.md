# Production Deployment Guide

This guide describes how to deploy RepoMedic in production using Turso persistence, live cloud providers, and the validated TASK-091 fixture.

## Architecture and Topology

RepoMedic uses a single backend process topology in production.

The FastAPI application and the QueueWorker run together in one process. On startup, the lifespan handler executes startup recovery to transition interrupted runs to a failed state. Running multiple backend worker processes concurrently across distributed instances is unsafe without distributed worker lease locks because a restarting process would mark active runs of peer workers as failed. Preserving a single backend process guarantees deterministic lifecycle management and safe startup recovery.

Storage persistence is backed by remote Turso libSQL. The frontend is a Next.js application communicating with the backend over HTTP and Server Sent Events.

## Security Configuration

In production, RepoMedic enforces strict spending limits and endpoint protections:

1. Server Enforced Budgets: Global spending limits derive exclusively from server configuration via `REPOMEDIC_TOTAL_BUDGET_USD`. Client requests cannot manipulate global caps.
2. Disabled Internal Endpoints: The internal operation reservation endpoint `POST /api/runs/{id}/operations` is disabled in production returning HTTP 404.
3. Atomic Settlement: Budget settlements use atomic Compare And Swap updates. Conflicting concurrent settlements cannot overwrite committed amounts.

## Environment Configuration

### Backend Environment (`backend/.env`)

Configure backend environment variables in `backend/.env` or your process supervisor:

```bash
REPOMEDIC_ENV=production
REPOMEDIC_STORAGE_BACKEND=turso
TURSO_DATABASE_URL=libsql://[database-name]-[org-slug].turso.io
TURSO_AUTH_TOKEN=your_token_here
REPOMEDIC_TOTAL_BUDGET_USD=25.0
REPOMEDIC_MAX_RUN_USD=2.0
REPOMEDIC_APP_ORIGIN=https://[public-frontend-domain]
REPOMEDIC_WORKER_ENABLED=true
REPOMEDIC_USE_REAL_ENGINE=true
REPOMEDIC_MODE=live
TOKEN_FACTORY_BASE_URL=https://api.tokenfactory.us-central1.nebius.com/v1/
TOKEN_FACTORY_MODEL=nvidia/nemotron-3-super-120b-a12b
NEBIUS_API_KEY=your_nebius_api_key
NEBIUS_PROJECT_ID=your_nebius_project_id
NEBIUS_SANDBOX_IMAGE=python:3.12-bookworm
```

### Frontend Environment (`frontend/.env.local`)

Configure frontend environment variables in `frontend/.env.local`:

```bash
NEXT_PUBLIC_API_TRANSPORT=http
NEXT_PUBLIC_API_URL=/api
BACKEND_URL=http://127.0.0.1:8000
PORT=3000
```

When hosting the frontend and backend on distinct domains, configure `NEXT_PUBLIC_API_URL` to point to the public backend URL and ensure it includes the `/api` prefix (for example `https://api.example.com/api` or `/api` when proxying through Next.js rewrites). Frontend API client calls append endpoint routes such as `/runs` directly to this base URL, so omitting `/api` results in invalid routing. Ensure `REPOMEDIC_APP_ORIGIN` matches the public frontend domain for CORS authorization.

## Backend Service Deployment

Install backend dependencies and run database migrations:

```bash
cd backend
uv run python -c "from src.storage.turso_client import TursoClient; client = TursoClient(); client.health(); client.close()"
```

Start the single backend process:

```bash
cd backend
REPOMEDIC_ENV=production uv run uvicorn src.main:create_app --factory --host 0.0.0.0 --port 8000
```

Verify backend health and budget endpoints:

```bash
curl -s http://127.0.0.1:8000/api/budget/usage
curl -s http://127.0.0.1:8000/api/tasks
```

## Frontend Application Deployment

Build the Next.js production bundle:

```bash
cd frontend
NEXT_PUBLIC_API_TRANSPORT=http npm run build
```

Start the production frontend server:

```bash
cd frontend
PORT=3000 npm run start
```

## Public Access and Reachability Check

Before initiating any paid repair runs on the deployed instance:

1. Confirm the frontend loads at the public URL and renders `LIVE MODE (TURSO / NEBIUS)` in the navigation bar.
2. Verify that task discovery displays available curated tasks loaded from the backend.
3. Verify that the previous live run `run_466bde7e846a494b8414e6f973df97d1` hydrates when visiting `/?runId=run_466bde7e846a494b8414e6f973df97d1`.
4. Check that patch and evidence downloads function correctly through the public origin.
5. Once reachability and hydration are verified, the instance is ready for final browser acceptance.
