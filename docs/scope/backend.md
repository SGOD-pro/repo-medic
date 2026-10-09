# Backend (Package B)

## Slice B: Backend implementation

### 1. Local D1 migrations and bridge · needs a decision
Implement the D1 bridge repository and migrations.
**Done when:** The local D1 emulator initializes the schema and runs CRUD operations.
- [ ] Design it (spec): `/architect local d1 migrations and bridge`

### 2. Task, run, and history API · needs a decision
Public FastAPI routes for starting and reading runs.
**Done when:** The API validates contracts and persists runs in local D1.
- [ ] Design it (spec): `/architect task run history api`

### 3. FakeEngine queue and worker · needs a decision
One worker claiming queued runs and passing them to FakeEngine.
**Done when:** A queued run transitions to running and completes via FakeEngine.
- [ ] Design it (spec): `/architect fakeengine queue worker`

### 4. SSE, cancel, and artifacts · needs a decision
Server-Sent Events for run progress, cancellation endpoint, and artifact downloads.
**Done when:** Clients receive ordered events, can cancel, and download patches.
- [ ] Design it (spec): `/architect sse cancel artifacts`

### 5. Budget enforcement and restart · needs a decision
Atomic budget checks and worker restart recovery.
**Done when:** Overruns are rejected, and restarts fail interrupted runs gracefully.
- [ ] Design it (spec): `/architect budget enforcement and restart`
