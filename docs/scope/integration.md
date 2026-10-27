# Integration (Lead)

## K0: Foundation preparation

### 1. Shared contracts and skeletons · done
Pydantic and TypeScript contracts, configuration parser, fakes, and K0 checks. Code in `backend/` and `frontend/`.

## K1: Parallel package work · done

### 2. Standalone package slices · done
Teammates build against shared contracts.
- [x] Package C engine slices 1 to 4 complete and verified offline
- [x] Package B backend slices 1 to 3 complete (D1 bridge, API, FakeEngine worker)
- [x] Package B backend slice 4 (SSE, cancel, and artifacts) complete
- [x] Package B backend slice 5 (budget enforcement and restart) complete
- [x] Package A frontend lint resolved and HTTP transport integration verified

## Slice I: Checkpoints K2 to K5

### 3. K2: Connect real app and offline providers · done
Merge B and C, connect real Engine repair to QueueWorker with HostPorts, switch A to HTTP.
**Done when:** All K2 integration tests (success, failure, restart, cancel) pass offline.
- [x] Replace FakeEngine in QueueWorker with C real repair function and real HostPorts
- [x] Complete B slices 4 and 5 (SSE, cancel, artifacts, budgets, restart)
- [x] Verify K2 end to end scenarios offline

### 4. K3: Connect remote Turso persistence · done
Connect remote Turso libSQL database persistence.
**Done when:** The backend persists to the remote Turso database correctly while offline models run.
- [x] Design it (spec): [0007. Remote Turso persistence](../specs/0007-remote-turso-persistence.md)
- [x] Turso storage adapter and schema migrations implemented behind existing repository contracts
- [x] Local and unit storage tests verified (22 unit tests passing)
- [x] Remote Turso acceptance suite verified against live Turso database (all 7 remote tests passing)
- [x] Full stack browser HTTP UI acceptance suite verified all nine scenarios against persistent Turso backend
- [x] Historical Cloudflare D1 integration preserved: [0005. Remote Cloudflare D1 integration](../specs/0005-remote-cloudflare-d1-integration/index.md)

### 5. K4: Provider verification and live E2E · done
Verify inference keys, sandbox access, and run a capped live test.
**Done when:** One complete sequential task is run live and verified without regressions.
- [x] Design it (spec): [0006. Live provider integration and sequential repair](../specs/0006-live-provider-integration/index.md)
- [x] Build it: `/develop k4 live e2e`
  - [x] Provider preflight CLI check and contree-sdk installation (covers: AC-1, AC-13)
  - [x] ConTree sandbox adapter with snapshot checkpointing and explicit patch injection (covers: AC-2, AC-3, AC-6, AC-8, AC-12)
  - [x] Live adapter resolution and fail closed engine repair coordination (covers: AC-1, AC-4, AC-5, AC-7)
  - [x] Atomic budget reservations, cache hash filtering, and responsive cancellation (covers: AC-9, AC-10, AC-11)
  - [x] Unit tests with mock ConTree SDK and operator live sequential repair suite (covers: AC-1..AC-12)
  - [x] Live sequential repair run_k4_live_1792870515 succeeded against verified fixture repository
  - [x] Full stack browser HTTP UI acceptance suite verified all nine scenarios
  _Code in `backend/src/engine/contree_sandbox.py`, `backend/src/engine/repair.py`, `backend/src/worker.py`, `backend/src/preflight.py`, and `scripts/`._
- [x] Verify it: `/check verify k4 live e2e`
- [x] Test it: `/test k4 live e2e`
- [x] Review it (fresh model): `/check review k4 live e2e`

### 6. K5: Evaluation, deployment and recording · in progress
Evaluation manifest preparation, demo deployment readiness, and video recording.
**Done when:** Evaluation scenarios are bounded and verified, demo deployment is ready, and demo recording is complete.
- [x] Design it (spec): [0008. Deploy RepoMedic on AWS SAM and Vercel](../specs/0008-aws-sam-and-vercel-deployment.md)
- [x] Prepare evaluation manifest and run usage reconciliation: `/develop Prepare RepoMedic for bounded K5 evaluation`
  - [x] Derive estimated run allocation from operation ledger and reconcile $0.3500 allocation with API and UI
  - [x] Keep token counts, estimated allocations, and measured provider billing distinct
  - [x] Offline regression tests in test_storage.py and test_worker.mjs preventing zero summary for nonzero allocations
  - [x] Evaluation manifest with controlled sequential migration, encode/databases external project, and branch and refine scenario
  _Code in `fixtures/evaluation_manifest.json`, `fixtures/tasks/`, `backend/src/evaluation/`, `backend/tests/evaluation/`, and `db-worker/`._
