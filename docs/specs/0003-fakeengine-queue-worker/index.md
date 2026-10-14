# 0003. FakeEngine queue and worker

**Date**: 2026-10-11
**Status**: Accepted

## Summary

This build spec defines the background queue worker that processes queued repair tasks using FakeEngine. The worker runs as an asynchronous background task within the FastAPI lifespan context, polling Cloudflare D1 for queued runs and claiming them one at a time. It loads the task recipe, invokes FakeEngine with D1HostPorts to record events and budget operations, and updates the run to its terminal state with a final run finished event.

## Requirements

**User stories**:
* As a user, I want queued repair runs to be picked up automatically so that my upgrade tasks run to completion without manual triggering.
* As an operator, I want run states to reflect progress accurately in Cloudflare D1 so that clients can observe whether a run is queued, running, succeeded, or failed.
* As a developer, I want unhandled engine exceptions to fail gracefully so that a single failed run does not crash the background worker process.

**Acceptance criteria**:
* **AC-1**: Worker bridge `GET /api/runs` accepts an optional `state` query parameter (for example `?state=queued`), returning only runs matching the specified lifecycle state.
* **AC-2**: Background queue worker polls D1 periodically (every 1 second when idle) for runs in state `queued`, claiming at most 1 run concurrently.
* **AC-3**: Upon claiming a run, the worker transitions the run state in D1 from `queued` to `running` before passing control to the repair engine.
* **AC-4**: The worker constructs `RepairRequest`, loads `TaskRecipe` from the task record or fixture, builds `D1HostPorts`, and executes `await fake_engine.repair(request, recipe, host)`.
* **AC-5**: When `FakeEngine.repair` completes, the worker updates the run in D1 to its terminal state (`succeeded` or `failed`) with the final reason, and appends a `run.finished` event with payload `{state, reason}`.
* **AC-6**: If an unhandled exception occurs during execution, the worker catches the error, transitions the run state in D1 to `failed` with the error description as reason, appends a `run.finished` event, and continues the polling loop.
* **AC-7**: The queue worker starts automatically during FastAPI application startup via lifespan, cancels and drains cleanly during application shutdown, and provides a standalone entrypoint for direct script invocation or test execution.

## Decision

**Chosen option**: Option 1: In process background worker task using D1 state polling

The worker runs as an `asyncio` task managed by FastAPI lifespan, polling D1 for runs in state `queued` and using an atomic state transition to claim work.

## Rationale

Reasoning and options: see [rationale.md](rationale.md).

## Feature design

**Data model sketch**:
The feature uses existing database tables without introducing new schema migrations:
* `runs`: state transitions from `queued` to `running` to `succeeded` or `failed`.
* `events`: sequence of execution events (`stage.completed`, `usage.updated`, `candidate.completed`, `run.finished`).
* `operations`: atomic budget reservations and settlements (`model:1`).
* `tasks`: stores repository and task metadata including `recipe_json`.

**State transitions**:
`queued` -> `running` -> `succeeded` (on successful engine completion)
`queued` -> `running` -> `failed` (on budget denial, test failure, or unhandled exception)
`queued` -> `running` -> `cancelled` (if cancelled via host ports)

**API surface**:
| Endpoint | Method | Key inputs | Key outputs | Auth | Key errors |
|---|---|---|---|---|---|
| /api/runs | GET | state:string (opt), limit:int (opt), task_id:string (opt) | runs array | bearer | 400 invalid param |
| /api/runs/{id} | PATCH | state:string (req), reason:string (opt) | ok boolean | bearer | 404 missing, 409 terminal state |
| /api/runs/{id}/events | POST | type:string (req), payload:object (req) | ok boolean, seq int | bearer | 400 invalid type, 404 missing run |

**Value sourcing**:
| Action | Value produced / displayed | Source |
|---|---|---|
| Claim run | run_id, task_id, mode, search_mode | Sourced from D1 runs table where state is queued |
| Load recipe | TaskRecipe instance | Sourced from tasks table recipe_json or fixture JSON file |
| Build request | RepairRequest instance | Sourced from claimed run fields (run_id, task_id, mode, search_mode) |
| Execute engine | RepairResult (state, reason) | Sourced from fake_engine.repair return value |
| Finalize run | Terminal state and reason in D1 | Sourced from RepairResult state and reason |
| Emit run.finished | Event sequence and payload | Sourced from D1 sequence generator and RepairResult summary |

**Key invariants**:
* Concurrency limit of 1: the local worker processes at most one run at a time to prevent CPU and port contention.
* Terminal state immutability: once a run transitions to `succeeded`, `failed`, or `cancelled`, it cannot be modified.
* Reliable final event: every claimed run must result in a terminal run state and a final `run.finished` event in the events log.

**Security model**:
* Internal service communication uses the existing shared bridge bearer token (`local-bridge-token` in development).
* Worker runs in process with backend privileges, respecting tenant and run boundaries.

**Configuration required**:
* `REPOMEDIC_WORKER_POLL_INTERVAL_SECONDS`: float (optional, default 1.0), interval between queue polling queries when idle.
* `REPOMEDIC_WORKER_ENABLED`: bool (optional, default true), flag allowing background worker loop to be disabled during isolated unit tests.

**Critical test scenarios**:
* Happy path: queued run is claimed, transitions to running, FakeEngine emits stages and budget updates, run reaches state succeeded with run.finished event, verifies **AC-1**, **AC-2**, **AC-3**, **AC-4**, **AC-5**.
* Failure case: engine raises an unhandled exception, worker catches error, updates run state to failed with descriptive reason, verifies **AC-6**.
* Lifespan lifecycle: FastAPI startup initializes the worker task, and application shutdown cancels and drains the task cleanly, verifies **AC-7**.

## Build plan

- [x] 1. Add `state` query parameter filtering to `GET /api/runs` in worker bridge and `RepoMedicDB`, satisfies **AC-1**
- [x] 2. Implement `TaskRecipe` loader helper to extract recipe information from task records or fixture files, satisfies **AC-4**
- [x] 3. Create `QueueWorker` class with polling loop, atomic claim transition from queued to running, and single concurrency limit, satisfies **AC-2**, **AC-3**
- [x] 4. Integrate `FakeEngine.repair` execution with `D1HostPorts` and terminal state completion handler emitting `run.finished`, satisfies **AC-4**, **AC-5**
- [x] 5. Add unhandled exception recovery ensuring failed runs are recorded with reason and final event, satisfies **AC-6**
- [x] 6. Wire worker startup and graceful cancellation into FastAPI application lifespan, plus standalone CLI helper, satisfies **AC-7**
- [x] 7. Write end to end integration tests proving queued run executes to completion, satisfies **AC-1**, **AC-2**, **AC-3**, **AC-4**, **AC-5**, **AC-6**, **AC-7**

## Consequences

**Positive**:
* Enables end to end task execution from queueing to completion without requiring external message brokers like RabbitMQ or Redis.
* Persists full audit trail of stage transitions and budget usage in Cloudflare D1.
* Maintains simplicity by running in process during local development while keeping worker logic modular.

**Negative / tradeoffs**:
* Periodic database polling adds small read query traffic every 1 second when the queue is idle.
* In process execution means heavy repair tasks share CPU resources with the web API server.

**Neutral**:
* Production deployment with multi worker pools will require advisory locking or Cloudflare Queues in future slices.

## Follow-up

- [ ] Add metric reporting for queue wait time and repair execution duration in observability slice.
