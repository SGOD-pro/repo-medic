# Production Deployment Guide

This guide describes how to deploy RepoMedic in production using Turso persistence and the validated TASK-091 fixture.

## Architecture and Topology

RepoMedic uses a single backend process topology in production.

The FastAPI application and the QueueWorker run together in one process. On startup, the lifespan handler executes startup recovery to transition interrupted runs to a failed state. Running multiple backend worker processes concurrently across distributed instances is unsafe without distributed worker lease locks because a restarting process would mark active runs of peer workers as failed. Preserving a single backend process guarantees deterministic lifecycle management and safe startup recovery.

Storage persistence is backed by remote Turso libSQL. The frontend is a Next.js application communicating with the backend over HTTP and Server Sent Events.

## Security Configuration

In production, RepoMedic enforces strict spending limits and endpoint protections:

1. Server Enforced Budgets: Global spending limits derive exclusively from server configuration via `REPOMEDIC_TOTAL_BUDGET_USD`. Client requests cannot manipulate global caps.
2. Disabled Internal Endpoints: The internal operation reservation endpoint `POST /api/runs/{id}/operations` is disabled in production returning HTTP 404.
3. Atomic Settlement: Budget settlements use atomic Compare And Swap updates. Conflicting concurrent settlements cannot overwrite committed amounts.

## Environment Variables

Configure backend environment variables in `backend/.env` or your process supervisor:

```bash
REPOMEDIC_ENV=production
REPOMEDIC_STORAGE_BACKEND=turso
TURSO_DATABASE_URL=libsql://[database-name]-[org-slug].turso.io
TURSO_AUTH_TOKEN=your_token_here
REPOMEDIC_TOTAL_BUDGET_USD=25.0
REPOMEDIC_MAX_RUN_USD=2.0
REPOMEDIC_APP_ORIGIN=http://localhost:3000
REPOMEDIC_WORKER_ENABLED=true
REPOMEDIC_USE_REAL_ENGINE=true
REPOMEDIC_MODE=offline
```

Configure frontend environment variables in `frontend/.env.local`:

```bash
NEXT_PUBLIC_API_TRANSPORT=http
PORT=3000
```

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

Verify backend health:

```bash
curl -s http://127.0.0.1:8000/api/budget/usage
```

## Frontend Application Deployment

Build the Next.js production bundle:

```bash
cd frontend
npm run build
```

Start the production frontend server:

```bash
cd frontend
PORT=3000 npm run start
```

## Validation Using TASK-091 Fixture

The production deployment automatically loads and synchronizes curated task definitions from `fixtures/tasks/` on startup.

The fixture `TASK-091` validates dependency upgrade migration for sqlalchemy from version 1.4.48 to 2.0.19.

1. Open the web UI at `http://localhost:3000`.
2. Verify TASK-091 is visible in the task list.
3. Select TASK-091 and trigger a repair run.
4. Verify execution progress, live events stream, and terminal outcome.
5. Confirm generated patch and evidence downloads are accessible.
