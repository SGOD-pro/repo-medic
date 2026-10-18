# Verification Guide: Remote Cloudflare D1 integration

This guide describes the operator commands, safety checklists, and acceptance verification protocol for checkpoint K3. Follow these steps when deploying and validating the remote Cloudflare D1 integration.

## 1. Preflight target verification

Before running any remote commands, verify operator credentials, account scope, and database configuration.

```bash
# 1. Verify operator identity and account access
npx wrangler whoami

# 2. Inspect target database details
npx wrangler d1 info repomedic-db

# 3. Ensure wrangler.toml database_id is configured with the real D1 UUID
# database_id must not equal 00000000-0000-0000-0000-000000000000
grep "database_id" db-worker/wrangler.toml
```

Preflight checks must confirm:
* The active Cloudflare account owns the D1 database instance named `repomedic-db`.
* The `database_id` in `db-worker/wrangler.toml` matches the real remote database UUID.
* The binding name is `DB`.

## 2. Remote schema and migration compatibility

Inspect the existing remote database state to confirm compatibility before applying migrations.

```bash
# 1. List migration status on remote D1
cd db-worker && npx wrangler d1 migrations list repomedic-db --remote

# 2. Inspect existing tables in remote D1
npx wrangler d1 execute repomedic-db --remote --command "SELECT name FROM sqlite_master WHERE type='table';"

# 3. Apply pending migrations
npx wrangler d1 migrations apply repomedic-db --remote
```

Compatibility rules:
* Migration `0001_initial_schema.sql` creates tables `runs`, `events`, `artifacts`, `operations`.
* Migration `0002_tasks_table.sql` creates table `tasks`.
* If tables already exist, verify that columns and check constraints match `docs/DATABASE.md` without destructive drops.

## 3. Safe secret provisioning and Worker deployment order

To ensure the remote Worker fails closed and never exposes the database, follow this strict deployment sequence:

```bash
# Step 1: Provision the secret authorization token BEFORE deploying code
# Use a high entropy token string; never commit this token to git
cd db-worker && npx wrangler secret put DB_BRIDGE_TOKEN

# Step 2: Deploy the Worker bridge to Cloudflare edge
npx wrangler deploy

# Step 3: Verify fail closed behavior
# If DB_BRIDGE_TOKEN is ever unconfigured, requests must return HTTP 500 or 401
# It must NEVER fall back to local-bridge-token on remote deployments
```

Verification of deployed Worker:
```bash
# 1. Probe unauthenticated health endpoint (must return HTTP 200)
curl -s -i https://repomedic-db-worker.<your-subdomain>.workers.dev/health

# 2. Probe data endpoint without token (must return HTTP 401 Unauthorized)
curl -s -i https://repomedic-db-worker.<your-subdomain>.workers.dev/api/tasks

# 3. Probe data endpoint with invalid token (must return HTTP 401 Unauthorized)
curl -s -i -H "Authorization: Bearer invalid-token" \
  https://repomedic-db-worker.<your-subdomain>.workers.dev/api/tasks

# 4. Probe data endpoint with valid token (must return HTTP 200 with tasks list)
curl -s -i -H "Authorization: Bearer <DB_BRIDGE_TOKEN>" \
  https://repomedic-db-worker.<your-subdomain>.workers.dev/api/tasks
```

## 4. Backend environment and isolation configuration

Configure the Python backend in `backend/.env` (or environment variables) to target the remote bridge with full acceptance isolation:

```env
# Backend remote D1 configuration
REPOMEDIC_DB_WORKER_URL=https://repomedic-db-worker.<your-subdomain>.workers.dev
REPOMEDIC_DB_WORKER_TOKEN=<DB_BRIDGE_TOKEN>
DB_BRIDGE_TOKEN=<DB_BRIDGE_TOKEN>

# Safety constraints: keep model and sandbox offline
REPOMEDIC_MODE=offline
REPOMEDIC_USE_REAL_ENGINE=true
REPOMEDIC_WORKER_ENABLED=true

# Remote acceptance isolation settings
# Prevent startup fixture sync from modifying existing remote tasks
REPOMEDIC_SYNC_FIXTURES=false
# Scope interrupted run recovery and queue worker polling to test prefix
REPOMEDIC_ACCEPTANCE_PREFIX=run_k3_accept_
```

Ensure the frontend has zero exposure to `DB_BRIDGE_TOKEN`. The frontend communicates exclusively with the backend HTTP API at `http://127.0.0.1:8000`.

## 5. Bounded acceptance test suite and exact manifest tracking

Run the dedicated remote acceptance test suite in `backend/`:

```bash
cd backend && uv run pytest tests/test_k3_remote_d1.py -v
```

The test runner tracks an exact in memory manifest of every entity created during the test run:
* `manifest["tasks"]`: list of specific `task_id` strings created.
* `manifest["runs"]`: list of specific `run_id` strings created.
* `manifest["operations"]`: list of specific `operation_id` strings created.
* `manifest["artifacts"]`: list of specific `artifact_id` strings created.

The suite executes the following checks using `D1HostPorts` and fake adapters:

1. **Isolation across startup paths**:
   Verifies that startup fixture sync does not mutate existing remote tasks, startup recovery inspects only runs matching the acceptance prefix, and queue worker polling claims only acceptance runs.

2. **Fail closed authentication verification**:
   Probes the bridge without tokens and with invalid tokens, verifying HTTP 401 rejection and confirming that dummy local tokens are never accepted on remote deployments.

3. **Transaction failure assertions (zero partial writes)**:
   * **Duplicate run insertion**: Attempting to insert a duplicate `run_id` returns HTTP 409 conflict. An assertion verifies that `SELECT COUNT(*) FROM runs WHERE run_id = ?` remains exactly 1, proving the original record was untouched.
   * **Invalid event sequence**: Attempting to append an event with a duplicate sequence number returns an error. An assertion verifies `SELECT COUNT(*) FROM events WHERE run_id = ?` confirms no partial or out of order event was stored.
   * **Oversized artifact boundary**: Uploading an artifact exceeding 1,048,576 bytes returns HTTP 400. An assertion verifies `SELECT COUNT(*) FROM artifacts WHERE artifact_id = ?` equals zero, proving no partial binary chunks remain.

4. **Concurrent budget reservation denial (per run and global)**:
   * **Per run budget cap**: For a run with `max_run_micro_usd` equal to 1,000,000 (1 USD), two concurrent `D1HostPorts.reserve` calls of 600,000 micro USD are dispatched in parallel. Exactly one succeeds (HTTP 201), and the second returns `False` (HTTP 409 conflict). An assertion confirms `SELECT SUM(reserved_micro_usd) FROM operations WHERE run_id = ?` equals exactly 600,000, proving no budget overrun occurred.
   * **Global budget cap (25 USD)**: Parallel reservations across multiple runs exceeding the 25 USD global cap (`repomedic_total_budget_usd = 25.0`) are dispatched simultaneously. Excess calls are rejected with HTTP 409 conflict. An assertion confirms the total committed micro USD across all operations in D1 remains strictly less than or equal to 25,000,000.

5. **Persistence across process restart**:
   Creates a run in state `running`. Terminates the backend process cleanly using `stopProcess`, verifies via direct bridge query that the run remains `running` in remote D1 while the backend is stopped, restarts the backend, and verifies that startup recovery marks only this acceptance run as `failed` with the restart reason.

6. **Event streaming and artifact integrity**:
   Emits sequential events via `D1HostPorts.emit` and verifies monotonic gap free sequence numbers. Stores patch and evidence artifacts via `D1HostPorts.save_artifact` and verifies decoded content matches the computed SHA256 checksum.

7. **User cancellation handling**:
   Cancels an active run and verifies state transitions to `cancelled`. Confirms `D1HostPorts.cancelled()` returns true and subsequent reservations or updates are rejected.

## 6. Exact manifest cleanup protocol

Broad pattern matching deletions (such as SQL `LIKE` queries) are prohibited. Cleanup deletes only the exact primary keys recorded in the invocation manifest:

```sql
-- Safe exact manifest cleanup queries
DELETE FROM operations WHERE operation_id IN (?1, ?2, ...);
DELETE FROM artifacts WHERE artifact_id IN (?1, ?2, ...);
DELETE FROM events WHERE run_id IN (?1, ?2, ...);
DELETE FROM runs WHERE run_id IN (?1, ?2, ...);
DELETE FROM tasks WHERE task_id IN (?1, ?2, ...);
```

Safety rules:
* Deletions must use exact parameter lists matching the in memory manifest.
* Never issue `DROP TABLE` or unconstrained deletions without an explicit `IN (...)` clause.
* If any test assertion fails, cleanup is aborted and the manifest is saved to `artifacts/k3_manifest_<timestamp>.json` so that operators can inspect or clean up the exact records during post failure analysis.

## 7. Failure recovery procedures

### Migration failure recovery
If `npx wrangler d1 migrations apply` fails:
1. Query migration history: `npx wrangler d1 execute repomedic-db --remote --command "SELECT * FROM d1_migrations;"`
2. Identify the failing statement. Because Cloudflare D1 executes each migration file inside an atomic transaction, an error automatically rolls back the entire file.
3. Correct the SQL migration script, commit the fix, and re-run the apply command.

### Worker deployment failure recovery
If `npx wrangler deploy` fails:
1. Wrangler retains the prior healthy deployment on the Cloudflare edge network.
2. If a bad version is accidentally deployed, roll back immediately:
   ```bash
   npx wrangler rollback
   ```
3. Verify bridge health via `curl https://repomedic-db-worker.<subdomain>.workers.dev/health`.

### Bridge connectivity troubleshooting
If the backend fails to connect to remote D1:
1. Probe `/health` endpoint from the backend host. If it times out or returns DNS failure, verify Cloudflare Worker routes and domain resolution.
2. If `/health` returns 200 but backend API calls return 401, verify that `REPOMEDIC_DB_WORKER_TOKEN` in `backend/.env` matches `DB_BRIDGE_TOKEN` configured via `wrangler secret put`.
3. If queries fail with database errors, inspect Worker logs via:
   ```bash
   cd db-worker && npx wrangler tail
   ```
