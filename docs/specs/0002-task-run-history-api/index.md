# 0002. Task, run, and history API

**Date**: 2026-10-11
**Status**: Accepted

## Summary

This build spec defines the public FastAPI web application for Package B. It exposes HTTP endpoints for listing available tasks, starting repair runs, inspecting individual run details, and querying run history. Incoming requests are validated against shared Pydantic contracts and persisted into local Cloudflare D1 storage through the database bridge. This provides the stable HTTP interface needed by frontend Package A while keeping task orchestration decoupled.

## Requirements

**User stories**:
* As a frontend developer, I want to fetch available tasks from `/api/tasks` so that users can choose a repository upgrade scenario.
* As a user, I want to trigger a repair run by sending `task_id` and `search_mode` to `/api/runs` so that RepoMedic queues my upgrade task.
* As a user, I want to query run details and browse past run history so that I can inspect run states and resource usage over time.

**Acceptance criteria**:
* **AC-1**: `GET /api/tasks` returns HTTP 200 with JSON payload containing an array of task summaries loaded from D1 storage.
* **AC-2**: `POST /api/runs` validates `task_id` and `search_mode`, creates a server issued identifier prefixed with `run_`, persists the new run in state `queued` to D1, and returns HTTP 202 with `RunSummary`.
* **AC-3**: `POST /api/runs` rejects missing or unknown tasks with HTTP 404 code `not_found`, and rejects invalid request bodies or unknown fields with HTTP 422 using the standard error envelope code `invalid_request`.
* **AC-4**: `GET /api/runs/{id}` returns HTTP 200 with `RunSummary` for an existing run, and returns HTTP 404 code `not_found` when the run identifier does not exist.
* **AC-5**: `GET /api/runs` returns HTTP 200 with an array of run summaries ordered descending by creation timestamp, supporting `limit` between 1 and 100 with default 50, and optional `task_id` filtering.
* **AC-6**: When communication with the D1 database worker fails or times out, the API returns HTTP 503 code `unavailable` using the standard error envelope without exposing internal stack traces.

## Decision

**Chosen option**: Option 1: FastAPI application with lifespan task synchronization and D1 repository integration.

We implement the public HTTP routes in `backend/src/main.py` using FastAPI, validating inputs with shared Pydantic contracts and mapping database operations through `D1StorageRepository`.

## Rationale

Reasoning, options considered, and forces: see [rationale.md](./rationale.md).

## Feature design

**Data model sketch**:

```sql
-- D1 tasks table
CREATE TABLE IF NOT EXISTS tasks (
  task_id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  repository_url TEXT NOT NULL,
  commit_sha TEXT NOT NULL,
  dependency TEXT NOT NULL,
  from_version TEXT NOT NULL,
  to_version TEXT NOT NULL,
  recipe_json TEXT,
  created_at TEXT NOT NULL
);

-- Existing D1 runs table (referenced by foreign key)
-- runs(run_id PK, task_id FK references tasks(task_id), mode, search_mode, state, reason, usage_json, created_at, updated_at, max_run_micro_usd)
```

**State transitions**:

Run lifecycle states:
`queued` -> `running` -> terminal state (`succeeded`, `failed`, or `cancelled`).
This API creates runs in `queued` state. Subsequent transitions occur when orchestration workers claim and execute runs.

**API surface**:

| Endpoint | Method | Key inputs | Key outputs | Auth | Key errors |
|---|---|---|---|---|---|
| `/api/tasks` | GET | none | `{tasks: TaskSummary[]}` | none | 500, 503 |
| `/api/runs` | POST | `task_id` (req), `search_mode` (req) | `RunSummary` | none | 404 not found, 422 invalid request, 503 unavailable |
| `/api/runs/{id}` | GET | `id` (path, req) | `RunSummary` | none | 404 not found, 503 unavailable |
| `/api/runs` | GET | `limit` (opt, int), `task_id` (opt, str) | `{runs: RunSummary[]}` | none | 422 invalid request, 503 unavailable |

**Value sourcing**:

| Action | Value produced or displayed | Source |
|---|---|---|
| GET `/api/tasks` | task metadata array | D1 tasks table queried via database bridge |
| POST `/api/runs` | `run_id` | Server generated opaque UUID formatted as `run_<uuid4_hex>` |
| POST `/api/runs` | `mode` | Server configuration `settings.repomedic_mode` defaulting to offline |
| POST `/api/runs` | `state` | Hardcoded initial state `queued` |
| POST `/api/runs` | `usage` | Initialized counters with zeros and estimated USD 0.0 |
| POST `/api/runs` | `artifacts` | Initialized empty array |
| GET `/api/runs/{id}` | `RunSummary` fields | Joined record from D1 `runs` and `artifacts` tables |
| GET `/api/runs` | `runs` array | D1 `runs` table ordered descending by `created_at` |
| Error responses | `error.code` and `error.message` | Unified exception handler mapping HTTP status to standard error envelope |

**Key invariants**:

* Every run references a verified `task_id` existing in the D1 tasks table.
* Public API responses always wrap errors in `{error: {code: string, message: string}}`.
* Request validation rejects extraneous unknown JSON fields to prevent unexpected parameters.
* All stored and transmitted timestamps use UTC in ISO 8601 format.

**Security model**:

* No user session cookies or passwords are required for local development operations.
* CORS middleware is enabled for local frontend origins (`http://localhost:3000` and `http://127.0.0.1:3000`).
* Internal tokens and database bridge secrets are kept strictly server side and never emitted in API responses.

**Configuration required**:

* `REPOMEDIC_DB_WORKER_URL`: Base URL of the database worker bridge (defaults to `http://127.0.0.1:8787`).
* `DB_BRIDGE_TOKEN`: Shared secret bearer token for worker bridge authorization.
* `REPOMEDIC_MODE`: Default run execution mode (defaults to `offline`).

**Critical test scenarios**:

* Happy path: Client requests `/api/tasks` then posts valid run payload to `/api/runs`, verifies **AC-1**, **AC-2**
* Failure case (missing task): Client posts run referencing non existent task identifier, receives HTTP 404 with code `not_found`, verifies **AC-3**
* Failure case (invalid payload): Client sends unknown JSON attributes or invalid search mode, receives HTTP 422 with code `invalid_request`, verifies **AC-3**
* Single run query: Client queries `/api/runs/{id}` for created run and non existent run, verifies **AC-4**
* Run history query: Client queries `/api/runs` with limit parameter, verifies **AC-5**
* Bridge outage: Client makes requests while database bridge is stopped, receives HTTP 503 with code `unavailable`, verifies **AC-6**

## Build plan

1. Add `fastapi` and `uvicorn` dependencies to `backend/pyproject.toml` and sync environment, satisfies **AC-2**
2. Add D1 migration `0002_tasks_table.sql` and Worker bridge endpoints for tasks queries and run listing, satisfies **AC-1**, **AC-5**
3. Implement task synchronization logic on startup lifespan reading JSON files from `fixtures/tasks/`, satisfies **AC-1**
4. Add global exception handlers in FastAPI translating validation and HTTP errors into unified `APIErrorEnvelope`, satisfies **AC-3**, **AC-6**
5. Implement FastAPI route handlers for `/api/tasks`, `POST /api/runs`, `GET /api/runs/{id}`, and `GET /api/runs`, satisfies **AC-1**, **AC-2**, **AC-4**, **AC-5**
6. Write automated offline unit and integration tests covering all endpoints and failure scenarios, satisfies **AC-1**, **AC-2**, **AC-3**, **AC-4**, **AC-5**, **AC-6**

## Consequences

**Positive**:
* Frontend Package A obtains a clear, documented HTTP contract for tasks and runs.
* Strict input validation with Pydantic prevents bad states from entering D1.
* Error handling provides clean, predictable error envelopes without traceback leaks.

**Negative / tradeoffs**:
* Adding FastAPI introduces an external web framework dependency to the backend package.
* Storing tasks in D1 requires an extra schema migration and startup synchronization step.

**Neutral**:
* Task definitions remain authored as JSON files in `fixtures/tasks/`, preserving fixture driven testing.

## Follow-up

* [ ] Coordinate with frontend Package A to verify contract compatibility on `/api/tasks` and `/api/runs`.
* [ ] Implement SSE streaming and cancellation routes in Slice B feature 4 once run orchestration worker is built.
