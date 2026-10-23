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

### 4. K3: Connect remote Cloudflare D1 · in progress
Deploy D1 bridge, apply migrations, set tokens.
**Done when:** The backend persists to the remote D1 correctly while offline models run.
- [x] Design it (spec): [0005. Remote Cloudflare D1 integration](../specs/0005-remote-cloudflare-d1-integration/index.md)
- [ ] Preflight target verification and remote schema inspection (offline verified, live CLI checks pending operator credentials)
- [ ] Deploy Worker bridge and configure backend tokens (offline verified, edge deployment pending operator credentials)
- [ ] Run remote acceptance suite with bounded records and cleanup (offline harness verified with 168 passed, remote opt in pending)
- [x] Review it: `/check review` findings resolved in [docs/reviews/2026-10-22-main.md](../reviews/2026-10-22-main.md)

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
  _Code in `backend/src/engine/contree_sandbox.py`, `backend/src/engine/repair.py`, `backend/src/worker.py`, `backend/src/preflight.py`, and `scripts/`._
- [x] Verify it: `/check verify k4 live e2e`
- [x] Test it: `/test k4 live e2e`
- [x] Review it (fresh model): `/check review k4 live e2e`

### 6. K5: Evaluation, deployment and recording · planned
Final evaluation checks, demo deployment, and video recording.
**Done when:** Application is deployed, evaluation complete, and recording is finished.
- [ ] Design it (spec): `/architect k5 deployment and recording`
