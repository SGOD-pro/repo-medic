# Production Deployment Guide

This guide describes how to deploy RepoMedic in production using Vercel for the frontend, an always running single process backend host for FastAPI and the embedded queue worker, remote Turso persistence, and live cloud providers.

## Architecture and Single Process Invariant

RepoMedic uses a single backend process topology in production.

The FastAPI application and the QueueWorker run together in one process. On startup, the lifespan handler executes startup recovery to transition interrupted runs to a failed state. Running multiple backend worker processes concurrently across distributed instances is unsafe without distributed worker lease locks because a restarting process would mark active runs of peer workers as failed. Preserving a single backend process guarantees deterministic lifecycle management and safe startup recovery.

Serverless functions that scale to zero or terminate background tasks on request completion cannot run the persistent queue worker. The backend must run on an always active container or virtual machine host.

Storage persistence is backed by remote Turso libSQL. The frontend is a Next.js application hosted on Vercel communicating with the backend over HTTPS and Server Sent Events.

## Backend Host Options, Costs, and Prerequisites

Because the backend requires an always active process with background task execution, evaluate the following host options:

### 1. Render Web Service (Recommended Managed Option)
* Plan Tier: Starter
* Monthly Cost: $7 USD
* Account Prerequisite: Render account linked to GitHub, payment card attached to account for Starter instances. Free tier instances sleep after fifteen minutes of inactivity, which would interrupt active repair pipelines and background queue polling, so the Starter plan is required.
* Build Command: `cd backend && uv sync`
* Start Command: `cd backend && uv run uvicorn src.main:create_app --factory --host 0.0.0.0 --port $PORT`

### 2. Railway Service
* Plan Tier: Hobby or Pro
* Monthly Cost: $5 to $10 USD (usage based calculation on 512 MB RAM and 0.5 CPU)
* Account Prerequisite: Railway account with billing method verified.
* Setup: Connect GitHub repository, configure root directory as `backend`, automated HTTPS provided.

### 3. Fly.io MicroVM
* Machine Size: `shared-cpu-1x` with 1024 MB RAM
* Monthly Cost: ~$5.70 USD
* Account Prerequisite: Fly.io account with credit card verified.
* Setup: Deploy using `fly.toml` with `auto_stop_machines = false` to guarantee continuous execution.

### 4. DigitalOcean Basic Droplet or App Platform
* Plan Tier: Basic
* Monthly Cost: $4 to $6 USD
* Account Prerequisite: DigitalOcean account with payment method.
* Setup: Container deployment or native Ubuntu LTS running systemd supervisor for the FastAPI process.

## Frontend Deployment on Vercel

* Platform: Vercel
* Plan Tier: Hobby (Free for open source and personal projects, $0 USD cost)
* Account Prerequisite: Vercel account linked to GitHub repository `SGOD-pro/repo-medic`.
* Root Directory: `frontend`
* Framework Preset: Next.js

### Frontend Environment Variables on Vercel

Configure these variables in your Vercel Project Settings under Environment Variables:

1. `NEXT_PUBLIC_API_TRANSPORT`: `http`
2. `NEXT_PUBLIC_API_URL`: `/api` (when proxying through Next.js rewrites) or `https://[your-backend-host]/api` (when calling backend directly)
3. `BACKEND_URL`: `https://[your-backend-host]` (used by `frontend/next.config.ts` rewrites to proxy `/api/:path*` to the backend)
4. `NEXT_PUBLIC_DOCS_URL`: `https://github.com/SGOD-pro/repo-medic`

## Backend Environment Configuration

Configure these environment variables in your backend hosting service:

```bash
REPOMEDIC_ENV=production
REPOMEDIC_STORAGE_BACKEND=turso
TURSO_DATABASE_URL=libsql://repo-medic-swyra-07.aws-ap-south-1.turso.io
TURSO_AUTH_TOKEN=[your-turso-token]
REPOMEDIC_TOTAL_BUDGET_USD=25.0
REPOMEDIC_MAX_RUN_USD=2.0
REPOMEDIC_APP_ORIGIN=https://[your-frontend-app].vercel.app
REPOMEDIC_WORKER_ENABLED=true
REPOMEDIC_USE_REAL_ENGINE=true
REPOMEDIC_MODE=live
TOKEN_FACTORY_BASE_URL=https://api.tokenfactory.us-central1.nebius.com/v1/
TOKEN_FACTORY_MODEL=nvidia/nemotron-3-super-120b-a12b
NEBIUS_API_KEY=[your-nebius-api-key]
NEBIUS_PROJECT_ID=[your-nebius-project-id]
NEBIUS_SANDBOX_IMAGE=python:3.12-bookworm
```

## Production Security, CORS, and Streaming Safeguards

1. Production HTTPS: All communication between browser, Vercel frontend, and backend host uses TLS encryption.
2. Permissive Vercel CORS: The FastAPI backend automatically permits cross origin requests from `https://.*\.vercel\.app` and explicit origins configured in `REPOMEDIC_APP_ORIGIN`.
3. Server Enforced Budgets: Global spending limits derive exclusively from server configuration via `REPOMEDIC_TOTAL_BUDGET_USD=25.0`. Client requests cannot alter budget limits.
4. Disabled Internal Endpoints: The internal operation reservation endpoint `POST /api/runs/{id}/operations` is disabled in production returning HTTP 404.
5. Server Sent Events Headers: Event streaming sets `Cache-Control: no-cache`, `Connection: keep-alive`, and `X-Accel-Buffering: no` to prevent buffering across reverse proxies and CDNs.

## Safe Public Demonstration Path for Judges

Judges evaluating RepoMedic can inspect the complete verified repair results without initiating paid cloud runs or depleting live budgets:

1. One Click Demo Banner: A dedicated banner at the top of the tasks dashboard highlights `TASK-091` (`run_93c660238e3443a6a18249167eb1939b`). Clicking View Validated Results navigates directly to the verification report.
2. Direct URL Hydration: Visiting `/?runId=run_93c660238e3443a6a18249167eb1939b` instantly hydrates the run from remote Turso storage.
3. Complete Evidence Inspection: The verification view displays 1/1 tests passing, 0 regressions, post patch test unchanged proof badges, unified change diff for `src/backend/database.py`, and addressable download buttons for `patch.diff`, `verify.log`, and `evidence.json`.
4. Independent Verification: The downloaded patch can be applied using `git apply --recount --whitespace=nowarn` against pinned commit `453a0b6c6b125177504cdd941902b8d48266ed1c` on `https://github.com/SGOD-pro/repo-medic.git` and passes pytest with exit code 0.

## Missing Hosting Access Status

No cloud deployment access tokens or provider CLI tools (such as Vercel tokens or Render, Railway, or Fly.io credentials) are configured in this environment.

To complete public hosting:
1. Link repository `SGOD-pro/repo-medic` to Vercel and your selected always running backend host (such as Render Starter).
2. Set the environment variables documented above.
3. Once the public URLs are live, run the public verification check before initiating any paid live repair through the public browser.
