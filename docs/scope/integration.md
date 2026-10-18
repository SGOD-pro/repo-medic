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

### 4. K3: Connect remote Cloudflare D1 · planned
Deploy D1 bridge, apply migrations, set tokens.
**Done when:** The backend persists to the remote D1 correctly while offline models run.
- [x] Design it (spec): [0005. Remote Cloudflare D1 integration](../specs/0005-remote-cloudflare-d1-integration/index.md)
- [ ] Preflight target verification and remote schema inspection
- [ ] Deploy Worker bridge and configure backend tokens
- [ ] Run remote acceptance suite with bounded records and cleanup

### 5. K4: Provider verification and live E2E · planned
Verify inference keys, sandbox access, and run a capped live test.
**Done when:** One complete sequential task is run live and verified without regressions.
- [ ] Design it (spec): `/architect k4 live e2e`

### 6. K5: Evaluation, deployment and recording · planned
Final evaluation checks, demo deployment, and video recording.
**Done when:** Application is deployed, evaluation complete, and recording is finished.
- [ ] Design it (spec): `/architect k5 deployment and recording`
