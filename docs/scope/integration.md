# Integration (Lead)

## K0: Foundation preparation

### 1. Shared contracts and skeletons · existing
Pydantic/TS contracts, config parser, fakes, and K0 checks. code in `backend/` and `frontend/`

## Slice I: Checkpoints K2–K5

### 2. K2: Connect real app and offline providers · needs a decision
Merge B and C, use public HTTP in A, FakeEngine replaced by real HostPorts.
**Done when:** All K2 integration tests (success, failure, restart, cancel) pass offline.
- [ ] Design it (spec): `/architect k2 offline integration`

### 3. K3: Connect remote Cloudflare D1 · needs a decision
Deploy D1 bridge, apply migrations, set tokens.
**Done when:** The backend persists to the remote D1 correctly while offline models run.
- [ ] Design it (spec): `/architect k3 remote d1`

### 4. K4: Provider verification and live E2E · needs a decision
Verify inference keys, sandbox access, and run a capped live test.
**Done when:** One complete sequential task is run live and verified without regressions.
- [ ] Design it (spec): `/architect k4 live e2e`

### 5. K5: Evaluation, deployment and recording · needs a decision
Final evaluation checks, demo deployment, and video recording.
**Done when:** Application is deployed, evaluation complete, and recording is finished.
- [ ] Design it (spec): `/architect k5 deployment and recording`
