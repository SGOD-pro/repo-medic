# Verify: Local D1 migrations and bridge, spec 0001, updated 2026-10-10
_Steps derived from spec 0001 acceptance criteria. /check verify runs these; /test locks the durable ones._

## UI / manual
- [x] Inspect local D1 database schema via wrangler sqlite introspection -> tables `runs`, `events`, `artifacts`, and `operations` exist with foreign keys and check constraints -> AC-1
- [x] Issue curl request to `/api/runs` with missing or incorrect Bearer header -> returns HTTP 401 with standard error envelope -> AC-2
- [x] Issue POST `/api/runs` then PATCH `/api/runs/:run_id` to `succeeded` -> subsequent PATCH returns HTTP 409 terminal state conflict -> AC-3
- [x] Post multiple events concurrently to `/api/runs/:run_id/events` -> sequence numbers start at 1 and increment with zero gaps -> AC-4
- [x] Post artifact exceeding 1,048,576 bytes -> returns HTTP 413 single artifact size limit exceeded -> AC-5
- [x] Post multiple artifacts totaling over 8,388,608 bytes -> returns HTTP 413 cumulative run storage limit exceeded -> AC-5
- [x] Reserve budget exceeding run limit -> returns HTTP 409 budget reservation limit exceeded -> AC-6

## Commands
- [x] `cd db-worker && npx wrangler d1 migrations apply repomedic-db --local` -> migrations apply cleanly with 8 commands -> AC-1
- [x] `cd db-worker && npx wrangler d1 execute repomedic-db --local --command "SELECT name FROM sqlite_master WHERE type='table';"` -> lists `runs`, `events`, `artifacts`, `operations` -> AC-1
- [x] `cd db-worker && node test_worker.mjs` -> all 9 test suites pass covering auth, runs, events, artifacts, and budgets -> AC-2, AC-3, AC-4, AC-5, AC-6
- [x] `cd backend && uv run mypy src` -> success with zero issues found in 10 source files -> AC-7
- [x] `cd backend && uv run flake8 src tests` -> zero lint errors reported -> AC-7
- [x] `cd backend && uv run pytest` -> all 12 storage and engine tests pass -> AC-3, AC-4, AC-5, AC-6, AC-7

## Value sourcing verification
- [x] POST `/api/runs` -> initial run record has usage initialized to zeros and timestamps from Worker clock -> Value sourcing 1
- [x] GET `/api/runs/:run_id` -> returns aggregated summary with joined artifacts from artifacts table -> Value sourcing 2
- [x] PATCH `/api/runs/:run_id` -> state transition confirmed and updated timestamp refreshed -> Value sourcing 3
- [x] POST `/api/runs/:run_id/events` -> sequence number derived atomically via `COALESCE(MAX(seq), 0) + 1` -> Value sourcing 4
- [x] GET `/api/runs/:run_id/events?after=1` -> returns chronological events where seq > after -> Value sourcing 5
- [x] POST `/api/runs/:run_id/artifacts` -> payload stored and cumulative volume validated against run capacity -> Value sourcing 6
- [x] GET `/api/runs/:run_id/artifacts/:artifact_id` -> exact stored base64 content returned -> Value sourcing 7
- [x] POST `/api/runs/:run_id/operations` -> reservation micro USD validated against remaining run capacity -> Value sourcing 8
- [x] PATCH `/api/operations/:operation_id` -> settled micro USD recorded and status set to settled -> Value sourcing 9

## Acceptance criteria coverage
- AC-1 (Schema migration and live emulator tables) covered by commands 1 and 2, manual step 1
- AC-2 (Service token bearer authentication) covered by command 3, manual step 2
- AC-3 (Runs CRUD and terminal state immutability) covered by command 3, command 6, manual step 3, value sourcing steps 1, 2, 3
- AC-4 (Atomic event sequencing and cursor listing) covered by command 3, command 6, manual step 4, value sourcing steps 4, 5
- AC-5 (Artifact storage and bounded size limits) covered by command 3, command 6, manual steps 5 and 6, value sourcing steps 6, 7
- AC-6 (Budget reservation limits and settlement) covered by command 3, command 6, manual step 7, value sourcing steps 8, 9
- AC-7 (Python db client and repository integration) covered by commands 4, 5, and 6
