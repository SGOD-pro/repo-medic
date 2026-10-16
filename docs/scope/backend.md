# Backend (Package B)

## Slice B: Backend implementation

### 1. Local D1 migrations and bridge · done
Implement the D1 bridge repository and migrations.
**Done when:** The local D1 emulator initializes the schema and runs CRUD operations.
- [x] Design it (spec): [0001](../specs/0001-local-d1-migrations-and-bridge/index.md)
- [x] Build it: `/develop local d1 migrations and bridge`
  - [x] Migration DDL and schema initialization in local D1 (AC-1)
  - [x] Worker bridge authentication, endpoints, and atomic constraints (AC-2, AC-3, AC-4, AC-5, AC-6)
  - [x] Python database client and repository helpers (AC-7)
  code in db-worker/ and backend/src/storage/
- [x] Verify it: `/check verify local d1 migrations and bridge`
- [x] Review it: `/check review` — findings in [docs/reviews/2026-10-10-backend.md](../reviews/2026-10-10-backend.md)

### 2. Task, run, and history API · done
Public FastAPI routes for starting and reading runs.
**Done when:** The API validates contracts and persists runs in local D1.
- [x] Design it (spec): [0002](../specs/0002-task-run-history-api/index.md)
- [x] Build it: `/develop task run history api`
  - [x] D1 tasks schema migration and Worker bridge query routes (AC-1, AC-5)
  - [x] FastAPI dependencies, startup lifespan task sync, and unified error handling (AC-1, AC-2, AC-3, AC-6)
  - [x] Route handlers for tasks, runs, and run history with integration tests (AC-1, AC-2, AC-4, AC-5)
  code in backend/src/ and db-worker/
- [x] Verify it: `/check verify task run history api`
- [x] Review it: `/check review` — findings in [docs/reviews/2026-10-11-backend.md](../reviews/2026-10-11-backend.md)

### 3. FakeEngine queue and worker · done
One worker claiming queued runs and passing them to FakeEngine.
**Done when:** A queued run transitions to running and completes via FakeEngine.
- [x] Design it (spec): [0003](../specs/0003-fakeengine-queue-worker/index.md)
- [x] Build it: `/develop fakeengine queue worker`
  - [x] Worker bridge state query parameter on runs (AC-1)
  - [x] TaskRecipe loader and QueueWorker single concurrency claiming loop (AC-2, AC-3)
  - [x] FakeEngine execution with D1HostPorts, terminal status update, and run.finished event (AC-4, AC-5, AC-6)
  - [x] FastAPI lifespan background task integration and standalone entrypoint (AC-7)
  code in backend/src/ and db-worker/
- [x] Verify it: `/check verify fakeengine queue worker`
- [x] Review it: `/check review` — findings in [docs/reviews/2026-10-12-backend.md](../reviews/2026-10-12-backend.md); holistic branch review in [docs/reviews/2026-10-14-backend.md](../reviews/2026-10-14-backend.md)

### 4. SSE, cancel, and artifacts · done
Server Sent Events for run progress, cancellation endpoint, and artifact downloads.
**Done when:** Clients receive ordered events, can cancel, and download patches.
- [x] Stream run events via GET /api/runs/{id}/events with cursor replay and heartbeats
- [x] Cancel queued or active runs via POST /api/runs/{id}/cancel
- [x] Download stored patch and log artifacts via GET /api/runs/{id}/artifacts/{artifact_id}
code in backend/src/main.py

### 5. Budget enforcement and restart · done
Atomic budget checks and worker restart recovery.
**Done when:** Overruns are rejected, and restarts fail interrupted runs gracefully.
- [x] Enforce total budget cap and rejection of invalid runs
- [x] Startup lifespan recovery of interrupted runs left in running state
code in backend/src/main.py
