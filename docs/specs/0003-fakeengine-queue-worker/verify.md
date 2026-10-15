# Verify: FakeEngine queue and worker, spec 0003, updated 2026-10-11
_Steps derived from spec 0003 acceptance criteria. /check verify runs these; /test locks the durable ones._

## UI / manual
- [x] Send GET request to `/api/runs?state=queued` -> returns HTTP 200 with runs matching queued state -> AC-1
- [x] Create a queued run via `POST /api/runs` and observe background worker polling loop picking it up -> state transitions to running -> AC-2, AC-3
- [x] Observe background worker executing `FakeEngine.repair` with `D1HostPorts` -> emits stage completed and usage updated events -> AC-4
- [x] Verify completed run in D1 reaches terminal state `succeeded` with `run.finished` event appended -> AC-5
- [x] Trigger repair run that encounters an error or exception -> verify run transitions to `failed` with descriptive reason and `run.finished` event -> AC-6
- [x] Verify worker starts automatically with FastAPI lifespan and cancels cleanly on server shutdown -> AC-7
- [x] Execute standalone worker entrypoint with a single run batch -> processes queued work to completion -> AC-7

## Commands
- [x] `cd backend && uv run flake8 src tests` -> zero lint errors reported -> AC-1 through AC-7
- [x] `cd backend && uv run mypy src tests` -> success with zero type errors in all source files -> AC-1 through AC-7
- [x] `cd backend && uv run pytest` -> all tests pass including queue worker unit and integration tests -> AC-1 through AC-7
- [x] `cd db-worker && node test_worker.mjs` -> all worker bridge tests pass including state query filtering -> AC-1

## Value sourcing verification
- [x] Claim run -> `run_id`, `task_id`, `mode`, `search_mode` sourced from queued run record in D1 -> Value sourcing 1
- [x] Load recipe -> `TaskRecipe` instance sourced from task fixture file or D1 task record -> Value sourcing 2
- [x] Build request -> `RepairRequest` instance constructed from claimed run fields -> Value sourcing 3
- [x] Execute engine -> `RepairResult` returned by `fake_engine.repair` -> Value sourcing 4
- [x] Finalize run -> terminal state and reason in D1 updated from `RepairResult` -> Value sourcing 5
- [x] Emit run.finished -> event sequence and payload recorded in D1 events table -> Value sourcing 6

## Acceptance criteria coverage
- AC-1 (Worker bridge state query parameter) covered by manual step 1, commands 3 and 4
- AC-2 (Queue worker polling loop and single concurrency) covered by manual step 2, command 3
- AC-3 (State transition from queued to running on claim) covered by manual step 2, command 3, value sourcing step 1
- AC-4 (Recipe loading and FakeEngine execution via D1HostPorts) covered by manual step 3, command 3, value sourcing steps 2, 3, 4
- AC-5 (Run finalization with terminal state and run.finished event) covered by manual step 4, command 3, value sourcing steps 5, 6
- AC-6 (Graceful handling of unhandled exceptions) covered by manual step 5, command 3
- AC-7 (FastAPI lifespan integration and standalone entrypoint) covered by manual steps 6 and 7, command 3

## Post review regression verification (updated 2026-10-12)
- [x] Trigger post state update error in `finish_run` -> verify `process_one` avoids double finish attempt and preserves terminal state -> Minor finding
- [x] Simulate concurrent terminal transition during engine execution -> verify 409 conflict handled gracefully without worker crash -> Minor finding
- [x] Run `backend && uv run pytest` with 44 tests passing and zero lint or type errors -> Regression check

## Post review verification (updated 2026-10-14)
- [x] Validate `run_id` format on `POST /api/runs` -> returns HTTP 400 for invalid characters or length > 128 -> Minor finding
- [x] Type annotations modernized in `main.py`, `repository.py`, and `contracts.py` -> Nits
- [x] Run `backend && uv run pytest` with all 45 tests passing, flake8 and mypy reporting 0 errors -> Regression check
- [x] Run `db-worker && node test_worker.mjs` with all bridge tests passing -> Regression check

