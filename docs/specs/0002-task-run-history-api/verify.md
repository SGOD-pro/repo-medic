# Verify: Task, run, and history API, spec 0002, updated 2026-10-11
_Steps derived from spec 0002 acceptance criteria. /check verify runs these; /test locks the durable ones._

## UI / manual
- [x] Send GET request to `/api/tasks` -> returns HTTP 200 with JSON payload containing array of task summaries -> AC-1
- [x] Send POST request to `/api/runs` with valid `task_id` and `search_mode` -> returns HTTP 202 with `RunSummary` prefixed with `run_` in queued state -> AC-2
- [x] Send POST request to `/api/runs` with unknown `task_id` -> returns HTTP 404 with error code `not_found` -> AC-3
- [x] Send POST request to `/api/runs` with invalid search mode or extraneous fields -> returns HTTP 422 with error code `invalid_request` -> AC-3
- [x] Send GET request to `/api/runs/{id}` for existing run -> returns HTTP 200 with `RunSummary` -> AC-4
- [x] Send GET request to `/api/runs/{id}` for non existent run -> returns HTTP 404 with error code `not_found` -> AC-4
- [x] Send GET request to `/api/runs` with limit parameter and optional `task_id` filter -> returns HTTP 200 with ordered run summaries array -> AC-5
- [x] Send GET request to `/api/runs` with invalid limit parameter such as 0 or 105 -> returns HTTP 422 with error code `invalid_request` -> AC-5
- [x] Send request to API when database bridge is unreachable -> returns HTTP 503 with error code `unavailable` without tracebacks -> AC-6
- [x] Inspect CORS response headers when Origin header is `http://localhost:3000` -> Access-Control-Allow-Origin header present -> Security model

## Commands
- [x] `cd backend && uv run flake8 src tests` -> zero lint errors reported -> AC-1 through AC-6
- [x] `cd backend && uv run mypy src tests` -> success with zero type errors in all source files -> AC-1 through AC-6
- [x] `cd backend && uv run pytest` -> all 23 tests pass covering storage, fake engine, and API routes -> AC-1 through AC-6
- [x] `cd db-worker && npx wrangler d1 execute repomedic-db --local --command "SELECT name FROM sqlite_master WHERE type='table';"` -> includes `tasks` and `runs` -> AC-1

## Value sourcing verification
- [x] GET `/api/tasks` -> task summaries array sourced from D1 tasks table -> Value sourcing 1
- [x] POST `/api/runs` -> `run_id` sourced from server UUID generator with prefix `run_` -> Value sourcing 2
- [x] POST `/api/runs` -> `mode` sourced from server configuration defaulting to offline -> Value sourcing 3
- [x] POST `/api/runs` -> initial run state set to `queued` -> Value sourcing 4
- [x] POST `/api/runs` -> usage counters initialized with zeros and USD 0.0 -> Value sourcing 5
- [x] POST `/api/runs` -> artifacts initialized with empty array -> Value sourcing 6
- [x] GET `/api/runs/{id}` -> run detail record joined with artifacts from D1 -> Value sourcing 7
- [x] GET `/api/runs` -> run summaries list ordered descending by creation timestamp -> Value sourcing 8
- [x] Error responses -> unified exception handlers format errors into standard error envelope -> Value sourcing 9

## Acceptance criteria coverage
- AC-1 (Task listing and startup synchronization) covered by manual step 1, commands 3 and 4, value sourcing step 1
- AC-2 (Run creation with server identifier and queued state) covered by manual step 2, command 3, value sourcing steps 2, 3, 4, 5, 6
- AC-3 (Rejection of missing tasks and invalid payloads) covered by manual steps 3 and 4, command 3, value sourcing step 9
- AC-4 (Single run detail query and 404 for missing identifiers) covered by manual steps 5 and 6, command 3, value sourcing step 7
- AC-5 (Run history listing with limit and task filter) covered by manual steps 7 and 8, command 3, value sourcing step 8
- AC-6 (Database bridge outage handling with 503 error envelope) covered by manual step 9, command 3, value sourcing step 9
