# Verification Guide: Remote Cloudflare D1 integration

This guide describes the operator commands and verification protocol for checkpoint K3. Follow these steps when deploying and validating the remote Cloudflare D1 integration.

## 1. Preflight target verification

Before running any remote commands, verify operator credentials, account scope, and database configuration.

```bash
# 1. Verify operator identity and account access
npx wrangler whoami

# 2. Inspect target database details
npx wrangler d1 info repomedic-db

# 3. Ensure wrangler.toml database_id is configured
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

## 3. Worker bridge deployment and secret provisioning

Deploy the private Worker bridge to Cloudflare and provision the shared service token.

```bash
# 1. Deploy Worker to Cloudflare edge
cd db-worker && npx wrangler deploy

# 2. Provision secret authorization token on remote Worker
# Use a high entropy token string; never commit this token to git
npx wrangler secret put DB_BRIDGE_TOKEN
```

Verification of deployed Worker:
```bash
# 1. Probe unauthenticated health endpoint (must return HTTP 200)
curl -s -i https://repomedic-db-worker.<your-subdomain>.workers.dev/health

# 2. Probe data endpoint without token (must return HTTP 401 Unauthorized)
curl -s -i https://repomedic-db-worker.<your-subdomain>.workers.dev/api/tasks

# 3. Probe data endpoint with valid token (must return HTTP 200 with tasks list)
curl -s -i -H "Authorization: Bearer <DB_BRIDGE_TOKEN>" \
  https://repomedic-db-worker.<your-subdomain>.workers.dev/api/tasks
```

## 4. Backend environment configuration

Configure the Python backend in `backend/.env` (or environment variables) to target the remote bridge:

```env
# Backend remote D1 configuration
REPOMEDIC_DB_WORKER_URL=https://repomedic-db-worker.<your-subdomain>.workers.dev
REPOMEDIC_DB_WORKER_TOKEN=<DB_BRIDGE_TOKEN>
DB_BRIDGE_TOKEN=<DB_BRIDGE_TOKEN>

# Safety constraints: keep model and sandbox offline
REPOMEDIC_MODE=offline
REPOMEDIC_USE_REAL_ENGINE=true
REPOMEDIC_WORKER_ENABLED=true
```

Ensure the frontend has zero exposure to `DB_BRIDGE_TOKEN`. The frontend communicates exclusively with the backend HTTP API at `http://127.0.0.1:8000`.

## 5. Bounded acceptance test suite

Run the dedicated remote acceptance test suite in `backend/`:

```bash
cd backend && uv run pytest tests/test_k3_remote_d1.py -v
```

The acceptance suite executes the following checks against remote D1:

1. **Unauthorized request rejection**:
   Confirms missing token and invalid token requests return HTTP 401 with standard error JSON.

2. **Persistence across process restart**:
   Creates run in remote D1 with state `running`. Shuts down backend process cleanly, confirms run remains `running` in remote D1 while backend is stopped, restarts backend, and verifies startup recovery marks run `failed` with restart reason.

3. **Event ordering and sequence integrity**:
   Emits multiple sequential events and confirms monotonic sequence numbers without gaps. Queries `/api/runs/:run_id/events?after=N` over WAN and confirms order and payload integrity.

4. **User cancellation handling**:
   Transitions active run to `cancelled` and confirms subsequent event emissions are rejected or handled idempotently.

5. **Artifact hash and limit enforcement**:
   Uploads patch diff and JSON evidence with computed SHA256 hashes. Fetches artifact by ID, decodes base64 content, and validates SHA256 checksum match. Probes 1 megabyte individual artifact limit and 8 megabytes total run volume limit, verifying HTTP 400 rejection on violation.

6. **Concurrent budget reservation denial**:
   Sends simultaneous parallel operation reservations exceeding `max_run_micro_usd`. Confirms atomic SQL transaction enforces spending cap and returns HTTP 409 conflict with code `budget_limit_exceeded`.

7. **Transactional failure behavior**:
   Simulates run failure and verifies run state transitions to `failed` with reason, failure event is recorded, settled operations are finalized, and no orphaned locks remain.

## 6. Targeted cleanup protocol

All test runs initiated during K3 testing use identifiers prefixed with `run_k3_remote_`:
Example: `run_k3_remote_1713400000_a1b2c3d4`

Cleanup is strictly constrained to this prefix:

```sql
-- Safe scoped cleanup script (executed via wrangler or client script)
DELETE FROM operations WHERE run_id LIKE 'run_k3_remote_%';
DELETE FROM artifacts WHERE run_id LIKE 'run_k3_remote_%';
DELETE FROM events WHERE run_id LIKE 'run_k3_remote_%';
DELETE FROM runs WHERE run_id LIKE 'run_k3_remote_%';
```

Safety constraints:
* Never execute `DROP TABLE` on remote D1.
* Never execute unconstrained `DELETE FROM runs` without a `WHERE run_id LIKE 'run_k3_remote_%'` clause.
* If a test fails, skip cleanup to preserve failure evidence for debugging unless `--force-cleanup` is passed.

## 7. Failure recovery procedures

### Migration failure recovery
If `npx wrangler d1 migrations apply` fails:
1. Query migration history: `npx wrangler d1 execute repomedic-db --remote --command "SELECT * FROM d1_migrations;"`
2. Identify the failing statement. Because D1 wraps each migration file in a transaction, incomplete migrations are automatically rolled back.
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
