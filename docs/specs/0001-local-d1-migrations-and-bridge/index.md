# 0001. Local D1 migrations and bridge

**Date**: 2026-10-10
**Status**: Accepted

## Summary

This build spec establishes the local database foundation for Package B using the Cloudflare D1 emulator. We create the initial schema migration and the private Cloudflare Worker bridge that handles database requests for the Python backend. The bridge runs offline during development, checks a shared service token, enforces data limits, and guards atomic updates like sequence numbers and budget caps. This allows our backend worker and API routes to store runs, events, artifacts, and spending records without touching any remote cloud resources.

## Requirements

**User stories**:
* As a backend developer, I want to initialize the D1 schema locally so that the application can persist runs, events, artifacts, and budget operations without internet access.
* As an orchestration worker, I want to send structured persistence requests to the private bridge so that durable events and artifacts survive application restarts.
* As a system operator, I want atomic checks on budget reservations and artifact sizes so that runs cannot exceed configured spending caps or storage limits.

**Acceptance criteria**:
* **AC-1**: The migration file `db-worker/migrations/0001_initial_schema.sql` creates all four required tables (`runs`, `events`, `artifacts`, `operations`), constraints, and indexes in the local D1 emulator without errors.
* **AC-2**: The Worker bridge validates the service token header (`Authorization: Bearer <DB_BRIDGE_TOKEN>`) on every request, returning a standard 401 error envelope when the token is missing or incorrect.
* **AC-3**: Run endpoints (`POST /api/runs`, `GET /api/runs/:run_id`, `PATCH /api/runs/:run_id`) create queued runs, retrieve stored run details with artifacts, and transition states while rejecting updates to terminal states (`succeeded`, `failed`, `cancelled`) with a 409 status code.
* **AC-4**: Event endpoints (`POST /api/runs/:run_id/events`, `GET /api/runs/:run_id/events`) atomically calculate sequence numbers starting at 1 for each run, and return ordered event lists filtered by the `after` query parameter.
* **AC-5**: Artifact endpoints (`POST /api/runs/:run_id/artifacts`, `GET /api/runs/:run_id/artifacts/:artifact_id`) store and retrieve base64 content while rejecting any single artifact larger than 1,048,576 bytes (1 megabyte) or total run artifact volume greater than 8,388,608 bytes (8 megabytes).
* **AC-6**: Operation endpoints (`POST /api/runs/:run_id/operations`, `PATCH /api/operations/:operation_id`) atomically check that reserved plus settled costs do not exceed the run spending limit (`max_run_micro_usd`), and settle actual costs idempotently.
* **AC-7**: The Python database client in `backend/src/storage/db_client.py` and repository helpers support all bridge routes and pass automated offline integration tests against the local D1 emulator.

## Decision

**Chosen option**: Option 1: Native TypeScript Worker router with raw SQL queries.

We implement the private Worker bridge using standard TypeScript and native Web APIs in `db-worker/src/index.ts`, executing explicit SQL queries against the local D1 database binding without adding extra routing or ORM dependencies.

## Feature design

**Data model sketch**:

```sql
-- db-worker/migrations/0001_initial_schema.sql

CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  mode TEXT NOT NULL,
  search_mode TEXT NOT NULL,
  state TEXT NOT NULL,
  reason TEXT,
  usage_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  max_run_micro_usd INTEGER NOT NULL CHECK (max_run_micro_usd >= 0)
);

CREATE INDEX IF NOT EXISTS idx_runs_state_created_at ON runs(state, created_at);

CREATE TABLE IF NOT EXISTS events (
  run_id TEXT NOT NULL REFERENCES runs(run_id),
  seq INTEGER NOT NULL CHECK (seq >= 1),
  ts TEXT NOT NULL,
  type TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  PRIMARY KEY (run_id, seq)
);

CREATE TABLE IF NOT EXISTS artifacts (
  artifact_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES runs(run_id),
  kind TEXT NOT NULL,
  filename TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
  content_base64 TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_artifacts_run_id ON artifacts(run_id);

CREATE TABLE IF NOT EXISTS operations (
  operation_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES runs(run_id),
  kind TEXT NOT NULL,
  status TEXT NOT NULL,
  reserved_micro_usd INTEGER NOT NULL CHECK (reserved_micro_usd >= 0),
  settled_micro_usd INTEGER CHECK (settled_micro_usd >= 0),
  provider_ref TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_operations_run_status ON operations(run_id, status);
```

**State transitions**:

Run state machine:
`queued` -> `running` -> terminal state (`succeeded`, `failed`, or `cancelled`).
Direct transition from `queued` to `cancelled` is permitted when a user cancels before a worker claims the run.
Once a run enters `succeeded`, `failed`, or `cancelled`, all further state transitions are rejected with HTTP 409 Conflict.

Operation state machine:
`reserved` -> `settled` (or `uncertain` if provider call state is unknown).
Reservations are never automatically deleted or refunded without explicit settlement.

**API surface**:

| Endpoint | Method | Key inputs | Key outputs | Auth | Key errors |
|---|---|---|---|---|---|
| /health | GET | None | status, ok | None | 500 internal error |
| /api/runs | POST | run_id, task_id, mode, search_mode, state, max_run_micro_usd | ok, run_id | Bearer | 400 invalid input, 401 unauthorized, 409 already exists |
| /api/runs/:run_id | GET | run_id in path | run_id, task_id, mode, search_mode, state, reason, usage, artifacts | Bearer | 401 unauthorized, 404 not found |
| /api/runs/:run_id | PATCH | state, reason | ok | Bearer | 400 invalid state, 401 unauthorized, 404 not found, 409 terminal state immutable |
| /api/runs/:run_id/events | POST | type, payload | ok, seq, ts | Bearer | 400 invalid payload, 401 unauthorized, 404 run not found |
| /api/runs/:run_id/events | GET | after (optional query integer) | events array | Bearer | 400 invalid cursor, 401 unauthorized, 404 run not found |
| /api/runs/:run_id/artifacts | POST | artifact_id, kind, filename, sha256, size_bytes, content_base64 | ok, artifact_id | Bearer | 401 unauthorized, 404 run not found, 413 size limit exceeded |
| /api/runs/:run_id/artifacts/:artifact_id | GET | run_id and artifact_id in path | artifact metadata and content_base64 | Bearer | 401 unauthorized, 404 not found |
| /api/runs/:run_id/operations | POST | operation_id, kind, reserved_micro_usd | ok | Bearer | 401 unauthorized, 404 run not found, 409 budget limit exceeded |
| /api/operations/:operation_id | PATCH | settled_micro_usd, provider_ref (optional) | ok | Bearer | 400 invalid amount, 401 unauthorized, 404 not found |

**Value sourcing**:

| Action | Value produced / displayed | Source |
|---|---|---|
| POST /api/runs | Initial run record | Input fields from caller, usage initialized to zeros, timestamps from Worker UTC clock |
| GET /api/runs/:run_id | Aggregated run summary | Core fields from runs table, artifacts list from artifacts table joined by run_id |
| PATCH /api/runs/:run_id | State transition confirmation | Target state from input, updated timestamp from Worker UTC clock |
| POST /api/runs/:run_id/events | Appended event sequence | Next sequence number derived atomically via `COALESCE(MAX(seq), 0) + 1` for that run_id, timestamp from Worker UTC clock |
| GET /api/runs/:run_id/events | Filtered event list | Chronological records from events table where seq is greater than after query parameter |
| POST /api/runs/:run_id/artifacts | Stored artifact confirmation | Metadata and base64 content from input, creation timestamp from Worker UTC clock, total volume verified against cumulative run sum |
| GET /api/runs/:run_id/artifacts/:id | Raw artifact payload | Exact stored base64 content and metadata from artifacts table |
| POST /api/runs/:run_id/operations | Reserved budget entry | Reservation micro USD from input, validated against run limit minus sum of active reservations |
| PATCH /api/operations/:id | Settled spend update | Final settled micro USD from input, status set to settled, updated timestamp from Worker UTC clock |

**Database client reference pattern**:

The Python client in `backend/src/storage/db_client.py` uses `httpx.Client` to interact with the Worker bridge. It passes bearer authentication on every call and provides clean helper methods for backend tasks:

```python
class RepoMedicDB:
    def __init__(self, base_url: str | None = None, api_key: str | None = None, timeout: float = 10.0):
        self.base_url = (base_url or settings.repomedic_db_worker_url).rstrip("/")
        self.api_key = api_key or settings.db_bridge_token
        self.timeout = timeout

    def _request(self, method: str, path: str, **kwargs) -> dict:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }
        with httpx.Client(timeout=self.timeout) as client:
            response = client.request(method, f"{self.base_url}{path}", headers=headers, **kwargs)
            response.raise_for_status()
            return response.json()

    def health(self) -> dict: ...
    def create_run(self, run_id: str, task_id: str, mode: str, search_mode: str, max_run_usd: float) -> dict: ...
    def get_run(self, run_id: str) -> dict: ...
    def update_run_state(self, run_id: str, state: str, reason: str | None = None) -> dict: ...
    def create_event(self, run_id: str, event_type: str, payload: dict) -> dict: ...
    def list_events(self, run_id: str, after: int = 0) -> list[dict]: ...
    def store_artifact(self, run_id: str, artifact_id: str, kind: str, filename: str, sha256: str, size_bytes: int, content_base64: str) -> dict: ...
    def get_artifact(self, run_id: str, artifact_id: str) -> dict: ...
    def reserve_budget(self, run_id: str, operation_id: str, kind: str, estimated_usd: float) -> dict: ...
    def settle_budget(self, operation_id: str, actual_usd: float) -> dict: ...
    def record_provider_ref(self, operation_id: str, provider_ref: str) -> dict: ...
```

**Key invariants**:

* The composite key `(run_id, seq)` is strictly unique and monotonic per run. Sequence numbers start at 1 with no gaps under standard sequential append operations.
* A run in a terminal state (`succeeded`, `failed`, `cancelled`) cannot be modified to any other state. The update query checks `state NOT IN ('succeeded', 'failed', 'cancelled')` and returns 409 Conflict if unchanged.
* Total artifact volume for any single run cannot exceed 8,388,608 bytes. The Worker calculates `SUM(size_bytes)` for existing run artifacts plus the incoming artifact size before saving.
* Individual artifact size cannot exceed 1,048,576 bytes. Incoming requests exceeding this limit fail immediately with code `artifact_size_limit_exceeded`.
* Active spend reservations cannot exceed `max_run_micro_usd`. The Worker calculates `SUM(CASE WHEN status = 'settled' THEN settled_micro_usd ELSE reserved_micro_usd END)` plus the new reservation before accepting.
* All error responses follow the standard JSON envelope: `{"error": {"code": string, "message": string}}`.

**Security model**:

* The Worker bridge is private infrastructure. It is not exposed directly to web browsers or external users.
* Every request must present `Authorization: Bearer <DB_BRIDGE_TOKEN>`. The Worker compares this header with the configured secret. If the token is missing or mismatched, access is denied with status 401.
* No user accounts, sessions, passwords, or cookies exist in the database or Worker bridge.
* Provider secrets and credentials must never be written to database tables or error logs.

**Configuration required**:

* `DB_BRIDGE_TOKEN`: Service secret string configured in Worker environment bindings (`db-worker/wrangler.toml` or `.dev.vars` for local development).
* `REPOMEDIC_DB_WORKER_URL`: Base URL string pointing to the Worker bridge (defaults to local emulator URL `http://127.0.0.1:8787` in offline development).
* `REPOMEDIC_DB_WORKER_TOKEN`: Python backend environment variable containing the matching service secret string used by `RepoMedicDB`.

**Critical test scenarios**:

* Happy path: Create a run, append multiple events, store an artifact, reserve budget, settle budget, and fetch run details end to end against the local emulator, verifies **AC-1**, **AC-3**, **AC-4**, **AC-5**, **AC-6**, **AC-7**.
* Failure case: Reject requests with an invalid bearer token with status 401, verifies **AC-2**.
* Failure case: Attempting to store an artifact larger than 1 megabyte fails with status 413, verifies **AC-5**.
* Failure case: Attempting to store artifacts exceeding 8 megabytes cumulative run volume fails with status 413, verifies **AC-5**.
* Failure case: Attempting to reserve budget exceeding the run limit fails with status 409, verifies **AC-6**.
* Failure case: Attempting to change state on a run that is already cancelled or succeeded fails with status 409, verifies **AC-3**.
* Concurrency case: Appending events in rapid sequence produces strictly ordered, unique sequence numbers starting at 1, verifies **AC-4**.

## Build plan

- [x] 1. Create migration file `db-worker/migrations/0001_initial_schema.sql` with table definitions, check constraints, foreign keys, and indexes, satisfies **AC-1**.
- [x] 2. Implement service token authentication middleware and standard error responses in `db-worker/src/index.ts`, satisfies **AC-2**.
- [x] 3. Implement runs endpoints (`POST /api/runs`, `GET /api/runs/:run_id`, `PATCH /api/runs/:run_id`) with terminal state immutability in `db-worker/src/index.ts`, satisfies **AC-3**.
- [x] 4. Implement event endpoints (`POST /api/runs/:run_id/events`, `GET /api/runs/:run_id/events`) with atomic sequence number incrementation and cursor filtering in `db-worker/src/index.ts`, satisfies **AC-4**.
- [x] 5. Implement artifact endpoints (`POST /api/runs/:run_id/artifacts`, `GET /api/runs/:run_id/artifacts/:artifact_id`) with individual and cumulative run volume bounds in `db-worker/src/index.ts`, satisfies **AC-5**.
- [x] 6. Implement budget operations endpoints (`POST /api/runs/:run_id/operations`, `PATCH /api/operations/:operation_id`) with atomic capacity verification and settlement in `db-worker/src/index.ts`, satisfies **AC-6**.
- [x] 7. Update Python `RepoMedicDB` in `backend/src/storage/db_client.py` and create storage repository helpers to cover all bridge endpoints with Pydantic validation, satisfies **AC-7**.
- [x] 8. Build automated offline test suite verifying migration execution, Worker API responses, and Python client integration against the local D1 emulator, satisfies **AC-1**, **AC-2**, **AC-3**, **AC-4**, **AC-5**, **AC-6**, **AC-7**.

## Follow-up

* [ ] Ask the lead owner to confirm whether `backend/src/config.py` should expose `repomedic_db_worker_token` as an alias for `db_bridge_token` to match `docs/PHASES.md`.
* [ ] Verify Wrangler local execution command flags in the repository Makefile for offline test runs.
