# 0005. Remote Cloudflare D1 integration

**Date**: 2026-10-18
**Status**: Proposed

## Summary

This build spec defines the remote Cloudflare D1 database connection for checkpoint K3. We deploy the private Cloudflare Worker bridge to Cloudflare edge infrastructure and connect the Python backend to the remote database over HTTPS. The deployment preserves completed K2 behavior, offline execution mode, and fake model adapters while verifying remote schema migrations, authorization tokens, restart persistence, and transactional budget reservations.

## Requirements

**User stories**:
* As an integration engineer, I want to verify our Cloudflare account, database identity, and Worker binding before deployment so that migrations apply only to the intended database.
* As a backend service, I want to persist runs, events, artifacts, and spending operations in remote Cloudflare D1 through a private token authorized bridge so that progress survives backend process restarts.
* As a system operator, I want bounded test records and targeted cleanup protocols so that remote verification tests never touch or destroy production data.

**Acceptance criteria**:
* **AC-1**: Preflight verification confirms the operator Cloudflare account, real D1 database identifier, and Worker binding before applying migrations or deploying code.
* **AC-2**: Remote schema inspection confirms compatibility with migration files `0001_initial_schema.sql` and `0002_tasks_table.sql`, ensuring zero breaking alterations to existing tables.
* **AC-3**: The Worker bridge deploys to Cloudflare edge infrastructure with secret token authorization, allowing access only to the backend while rejecting unauthorized requests with HTTP 401.
* **AC-4**: Remote acceptance testing uses uniquely prefixed run identifiers (`run_k3_remote_<timestamp>_<hex>`) and restricts cleanup strictly to those prefixed records without table drops or truncations.
* **AC-5**: Remote checks verify run state persistence across backend process restart, strictly ordered event streams, user cancellation, and artifact content retrieval with valid SHA256 hashes within size limits.
* **AC-6**: Concurrent budget reservations atomically reject attempts to exceed run spending limits with HTTP 409 conflict, and failed runs transition safely without dangling locks.
* **AC-7**: Failure recovery procedures document rollback steps for failed migrations, bad Worker deployments, and unreachable bridge endpoints.

## Decision

**Chosen option**: Option 1: Direct Cloudflare Worker bridge deployment with backend service token.

We deploy the existing TypeScript Worker in `db-worker/` directly to Cloudflare edge infrastructure bound to the real Cloudflare D1 database instance. The backend communicates over HTTPS using the secret `DB_BRIDGE_TOKEN` bearer header.

## Feature design

**Data model sketch**:

The remote schema matches `db-worker/migrations/` exactly:

```sql
-- Existing migrations applied to remote D1:
-- 0001_initial_schema.sql:
--   runs: run_id (PK), task_id, mode, search_mode, state, reason, usage_json, created_at, updated_at, max_run_micro_usd
--   events: run_id (FK), seq, ts, type, payload_json, PRIMARY KEY (run_id, seq)
--   artifacts: artifact_id (PK), run_id (FK), kind, filename, sha256, size_bytes, content_base64, created_at
--   operations: operation_id (PK), run_id (FK), kind, status, reserved_micro_usd, settled_micro_usd, provider_ref, created_at, updated_at
-- 0002_tasks_table.sql:
--   tasks: task_id (PK), title, repository_url, commit_sha, dependency, from_version, to_version, recipe_json, created_at
```

**State transitions**:

Run state transitions in remote D1:
`queued` → `running` → `succeeded` | `failed` | `cancelled`

Terminal states are immutable. Any attempt to mutate a terminal run returns HTTP 409 conflict.

**API surface**:

| Endpoint | Method | Key inputs | Key outputs | Auth | Key errors |
|---|---|---|---|---|---|
| `/health` | GET | none | `{"ok": true, "status": "healthy"}` | Public | 500 |
| `/api/runs` | POST | `run_id`, `task_id`, `mode`, `search_mode`, `max_run_micro_usd` | `{"ok": true, "run_id": string}` | Bearer token | 400, 401, 409 |
| `/api/runs/:run_id` | GET | `run_id` | Run object with usage and artifacts | Bearer token | 401, 404 |
| `/api/runs/:run_id` | PATCH | `state`, `reason` | `{"ok": true}` | Bearer token | 400, 401, 404, 409 |
| `/api/runs/:run_id/events` | POST | `type`, `payload` | `{"ok": true, "seq": number, "ts": string}` | Bearer token | 400, 401, 404, 409 |
| `/api/runs/:run_id/events` | GET | `after` (optional sequence cursor) | `{"events": array}` | Bearer token | 401, 404 |
| `/api/runs/:run_id/artifacts` | POST | `artifact_id`, `kind`, `filename`, `sha256`, `size_bytes`, `content_base64` | `{"ok": true, "artifact_id": string}` | Bearer token | 400, 401, 404 |
| `/api/runs/:run_id/artifacts/:id` | GET | `run_id`, `artifact_id` | Artifact object with base64 content | Bearer token | 401, 404 |
| `/api/runs/:run_id/operations` | POST | `operation_id`, `kind`, `reserved_micro_usd` | `{"ok": true}` | Bearer token | 400, 401, 404, 409 |
| `/api/operations/:id` | PATCH | `settled_micro_usd`, `provider_ref` | `{"ok": true}` | Bearer token | 400, 401, 404, 409 |

**Value sourcing**:

| Action | Value produced or displayed | Source |
|---|---|---|
| Target account check | Cloudflare Account ID and email | `npx wrangler whoami` CLI output |
| Target database check | Database UUID and binding name | `npx wrangler d1 info repomedic-db` and `wrangler.toml` |
| Remote schema inspection | Table inventory and migration list | Remote queries against `sqlite_master` and `d1_migrations` |
| Bridge URL configuration | `REPOMEDIC_DB_WORKER_URL` | Deployed Worker URL from `npx wrangler deploy` |
| Bridge token configuration | `REPOMEDIC_DB_WORKER_TOKEN` | Secret configured via `npx wrangler secret put DB_BRIDGE_TOKEN` |
| Acceptance record prefix | Unique run identifier | Formatted string `run_k3_remote_<timestamp>_<hex>` |
| Hash validation | Computed sha256 checksum | SHA256 digest of artifact raw content string |

**Key invariants**:
* Zero paid cloud provider calls: `REPOMEDIC_MODE` remains `offline`, preserving `FakeHost` and fake model adapters.
* Zero client credential exposure: The Next.js frontend never receives `REPOMEDIC_DB_WORKER_TOKEN` or `DB_BRIDGE_TOKEN`.
* Atomic sequence numbers: Event sequence numbers start at 1 and increment strictly without gaps per run.
* Artifact size ceiling: Individual artifacts must not exceed 1,048,576 bytes; total artifacts per run must not exceed 8,388,608 bytes.
* Budget guarantee: Total reserved plus settled operation amounts cannot exceed `max_run_micro_usd`.
* Targeted cleanup: Deletions during acceptance tests are strictly scoped by `run_id LIKE 'run_k3_remote_%'`.

**Security model**:
* The Worker bridge requires `Authorization: Bearer <token>` on all data endpoints.
* The secret token is stored in Cloudflare Worker encrypted environment secrets and backend environment files. It is excluded from source control.
* Public access is restricted strictly to the `/health` liveness probe.

**Configuration required**:
* `CLOUDFLARE_ACCOUNT_ID`: Cloudflare account identifier for deployment.
* `CLOUDFLARE_DATABASE_ID`: Real Cloudflare D1 database UUID replacing the zero UUID placeholder.
* `DB_BRIDGE_TOKEN`: Secret token set on the Worker via `wrangler secret put`.
* `REPOMEDIC_DB_WORKER_URL`: Public HTTPS endpoint of the deployed Worker bridge.
* `REPOMEDIC_DB_WORKER_TOKEN`: Matching backend authorization token.
* `REPOMEDIC_MODE`: Set to `offline` to ensure zero provider credit consumption.

**Critical test scenarios**:
* Target preflight check: Verifies `wrangler whoami` and `d1 info` match expected account and database IDs, satisfies **AC-1**.
* Schema compatibility check: Queries remote tables and checks migration status before deploying, satisfies **AC-2**.
* Unauthorized request rejection: Probes bridge endpoints with missing and invalid tokens, verifying HTTP 401, satisfies **AC-3**.
* Bounded acceptance run and cleanup: Executes end to end run with prefixed identifier and verifies scoped cleanup, satisfies **AC-4**.
* Process restart recovery: Shuts down backend while run is active and verifies startup recovery from remote D1, satisfies **AC-5**.
* Concurrent budget race check: Issues simultaneous parallel reservations exceeding spending caps and verifies HTTP 409 rejection, satisfies **AC-6**.
* Failure and rollback verification: Validates handling of simulated migration and deployment errors, satisfies **AC-7**.

## Build plan

1. Preflight verification script (`scripts/verify_k3_target.mjs`):
   Inspect Cloudflare account identity, database binding, and existing migrations without mutating remote data. Satisfies **AC-1**, **AC-2**.

2. Deployment configuration update (`db-worker/wrangler.toml` and secrets):
   Update `database_id` with real D1 UUID and document `DB_BRIDGE_TOKEN` secret provisioning. Satisfies **AC-1**, **AC-3**.

3. Remote acceptance test suite (`backend/tests/test_k3_remote_d1.py`):
   Implement comprehensive automated suite executing unauthorized checks, process restart persistence, event streaming, artifact SHA256 verification, and concurrent budget denial against remote D1 with isolated prefixed records and scoped cleanup. Satisfies **AC-3**, **AC-4**, **AC-5**, **AC-6**.

4. Operator recovery documentation (`docs/specs/0005-remote-cloudflare-d1-integration/verify.md`):
   Document exact step by step commands for preflight inspection, deployment, migration application, test execution, and rollback recovery. Satisfies **AC-7**.

## Consequences

**Positive**:
* Validates true remote persistence on Cloudflare edge before introducing live model provider credentials in K4.
* Exposes network latency, connection pooling, and Cloudflare D1 dialect characteristics early while tests are reproducible and free.
* Protects database integrity through scoped acceptance identifiers and automated preflight checks.

**Negative / tradeoffs**:
* Requires active Cloudflare account credentials and network connectivity during K3 acceptance runs.
* Remote network latency makes the K3 acceptance suite slower than local SQLite emulator tests.

**Neutral**:
* Local D1 development using `wrangler dev` remains fully supported for day to day offline work.

## Follow-up

- [ ] Run `scripts/verify_k3_target.mjs` with operator credentials before applying remote migrations.
- [ ] Tag git repository with `checkpoint-k3-d1-integrated` after remote acceptance suite passes.

## Rationale

See [rationale.md](rationale.md) for background context, forces considered, and alternative architectural approaches.
