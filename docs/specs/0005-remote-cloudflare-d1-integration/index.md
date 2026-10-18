# 0005. Remote Cloudflare D1 integration

**Date**: 2026-10-18
**Status**: Proposed

## Summary

This build spec defines the remote Cloudflare D1 database connection for checkpoint K3. We deploy the private Cloudflare Worker bridge to Cloudflare edge infrastructure and connect the Python backend to the remote database over HTTPS. The deployment preserves completed K2 behavior, offline execution mode, and fake model adapters while enforcing strict acceptance isolation, exact manifest record cleanup, fail closed secret authentication, and atomic transactional budget assertions.

## Requirements

**User stories**:
* As an integration engineer, I want isolated remote acceptance execution so that testing never modifies, recovers, or claims unrelated tasks and runs.
* As a database administrator, I want cleanup driven strictly by an exact invocation manifest so that only records created during that specific test run are removed.
* As a security engineer, I want the remote Worker to fail closed when its secret token is unconfigured, reserving dummy token fallbacks strictly for local development.
* As an orchestration worker, I want atomic per run and global budget reservations via D1HostPorts with concrete assertions proving zero partial writes on failure.

**Acceptance criteria**:
* **AC-1**: Preflight verification confirms the operator Cloudflare account, target database identifier, and Worker binding before applying migrations or deploying code.
* **AC-2**: Remote acceptance runs against an isolated dedicated database or enforces strict run prefix scoping across startup fixture sync, interrupted run recovery, and queue worker polling.
* **AC-3**: Worker bridge authentication fails closed on remote deployments if `DB_BRIDGE_TOKEN` is missing, returning HTTP 500 or 401 without falling back to local dummy tokens.
* **AC-4**: Remote acceptance testing tracks an exact manifest of every created task, run, operation, event, and artifact, and cleanup deletes only records in that exact manifest without broad pattern matching.
* **AC-5**: Acceptance assertions using D1HostPorts prove zero partial writes on failed run insertions, invalid event sequences, and oversized artifact payloads.
* **AC-6**: Concurrent parallel reservations verify that both per run budget caps and the global budget cap (25 USD) are atomically enforced, returning HTTP 409 conflict on excess requests.
* **AC-7**: Failure recovery documentation specifies deployment ordering (secrets before traffic), migration rollback procedures, and Worker rollback commands.

## Decision

**Chosen option**: Option 1: Direct Cloudflare Worker bridge deployment with fail closed authentication, scoped backend isolation, and exact manifest cleanup.

We deploy the existing TypeScript Worker in `db-worker/` directly to Cloudflare edge infrastructure bound to the real Cloudflare D1 database instance. The Worker enforces fail closed bearer token authentication. The backend interacts through `D1HostPorts` using fake model and sandbox adapters. Acceptance testing operates on a dedicated acceptance database or strictly scoped task and run namespaces with exact manifest cleanup.

## Feature design

**Isolation and scoping across backend paths**:

To prevent acceptance runs from altering unrelated tasks or runs in remote D1, isolation is enforced through two complementary mechanisms:

1. Dedicated acceptance database (Primary):
   Deploy the Worker bridge connected to a dedicated acceptance database instance (for example `repomedic-db-acceptance`), keeping test mutations physically separated from staging or production data.

2. Enforceable scoping through all backend paths (Secondary):
   When running acceptance checks against any shared database, all backend paths enforce an acceptance prefix (for example `run_k3_accept_<timestamp>_<hex>`):
   * Startup fixture sync: Gated via `REPOMEDIC_SYNC_FIXTURES=false` during acceptance runs, or restricted to inserting tasks with explicit acceptance IDs.
   * Interrupted run recovery: `recover_interrupted_runs` filters queries by the configured acceptance run prefix, ensuring it never touches or fails unrelated running tasks.
   * Queue worker polling: `QueueWorker` polls and claims only queued runs matching the configured acceptance prefix, preventing it from processing unrelated workloads.

**Exact manifest cleanup protocol**:

Broad pattern matching (such as SQL `LIKE` queries) is prohibited during cleanup. Instead, the acceptance test runner maintains an in memory execution manifest recording every entity created during the invocation:
* Exact `task_id` list
* Exact `run_id` list
* Exact `operation_id` list
* Exact `artifact_id` list

At test completion, cleanup issues explicit queries referencing only those exact identifiers:
```sql
DELETE FROM operations WHERE operation_id IN (?1, ?2, ...);
DELETE FROM artifacts WHERE artifact_id IN (?1, ?2, ...);
DELETE FROM events WHERE run_id IN (?1, ?2, ...);
DELETE FROM runs WHERE run_id IN (?1, ?2, ...);
DELETE FROM tasks WHERE task_id IN (?1, ?2, ...);
```
If a test check fails, cleanup is skipped and the manifest is written to `artifacts/k3_manifest_<timestamp>.json` to enable post failure inspection.

**Fail closed authentication and secret provisioning order**:

In `db-worker/src/index.ts`, authentication fails closed on remote deployments:
* If `env.DB_BRIDGE_TOKEN` is undefined, empty, or whitespace, `checkAuth` immediately rejects the request with HTTP 500 and code `auth_unconfigured`.
* The fallback to `local-bridge-token` is restricted strictly to local development (detected via local hostname or `env.ENVIRONMENT === "local"`).
* Deployment order requires provisioning the secret before routing live traffic:
  1. `npx wrangler secret put DB_BRIDGE_TOKEN` provisions the encrypted secret on Cloudflare.
  2. `npx wrangler deploy` deploys the Worker code.
  3. If code is deployed before secret provisioning, the Worker fails closed, protecting the database from unauthenticated access.
  4. Backend environment sets `REPOMEDIC_DB_WORKER_TOKEN` matching `DB_BRIDGE_TOKEN`.

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
| `/api/runs/:run_id/operations` | POST | `operation_id`, `kind`, `reserved_micro_usd`, `global_budget_micro_usd` | `{"ok": true}` | Bearer token | 400, 401, 404, 409 |
| `/api/operations/:id` | PATCH | `settled_micro_usd`, `provider_ref` | `{"ok": true}` | Bearer token | 400, 401, 404, 409 |

**Value sourcing**:

| Action | Value produced or displayed | Source |
|---|---|---|
| Target account check | Cloudflare Account ID and email | `npx wrangler whoami` CLI output |
| Target database check | Database UUID and binding name | `npx wrangler d1 info repomedic-db` and `wrangler.toml` |
| Remote schema inspection | Table inventory and migration list | Remote queries against `sqlite_master` and `d1_migrations` |
| Bridge URL configuration | `REPOMEDIC_DB_WORKER_URL` | Deployed Worker URL from `npx wrangler deploy` |
| Bridge token configuration | `REPOMEDIC_DB_WORKER_TOKEN` | Secret configured via `npx wrangler secret put DB_BRIDGE_TOKEN` |
| Acceptance manifest | Specific task, run, operation, artifact IDs | In memory tracking set generated by test runner |
| Hash validation | Computed sha256 checksum | SHA256 digest of artifact raw content string |

**Key invariants**:
* Zero paid cloud provider calls: `REPOMEDIC_MODE` remains `offline`, preserving `FakeHost` and fake model adapters.
* Zero client credential exposure: The Next.js frontend never receives `REPOMEDIC_DB_WORKER_TOKEN` or `DB_BRIDGE_TOKEN`.
* Atomic sequence numbers: Event sequence numbers start at 1 and increment strictly without gaps per run.
* Artifact size ceiling: Individual artifacts must not exceed 1,048,576 bytes; total artifacts per run must not exceed 8,388,608 bytes.
* Budget guarantee: Total reserved plus settled operation amounts cannot exceed `max_run_micro_usd` or the global budget cap (25 USD).
* Exact manifest cleanup: Only records listed in the invocation manifest are deleted. Broad pattern deletions are forbidden.

**Security model**:
* The Worker bridge requires `Authorization: Bearer <token>` on all data endpoints and fails closed if the secret is unconfigured.
* The secret token is stored in Cloudflare Worker encrypted environment secrets and backend environment files. It is excluded from source control.
* Public access is restricted strictly to the `/health` liveness probe.

**Configuration required**:
* `CLOUDFLARE_ACCOUNT_ID`: Cloudflare account identifier for deployment.
* `CLOUDFLARE_DATABASE_ID`: Real Cloudflare D1 database UUID replacing the zero UUID placeholder.
* `DB_BRIDGE_TOKEN`: Secret token set on the Worker via `wrangler secret put`.
* `REPOMEDIC_DB_WORKER_URL`: Public HTTPS endpoint of the deployed Worker bridge.
* `REPOMEDIC_DB_WORKER_TOKEN`: Matching backend authorization token.
* `REPOMEDIC_MODE`: Set to `offline` to ensure zero provider credit consumption.
* `REPOMEDIC_SYNC_FIXTURES`: Optional boolean controlling automatic task fixture synchronization on startup.

**Critical test scenarios**:
* Target preflight check: Verifies `wrangler whoami` and `d1 info` match expected account and database IDs, satisfies **AC-1**.
* Isolation check across backend paths: Verifies startup fixture sync, interrupted run recovery, and queue worker polling do not mutate or process unrelated tasks and runs, satisfies **AC-2**.
* Fail closed authentication: Verifies missing secret token rejects requests with HTTP 500 or 401 without falling back to local dummy tokens, satisfies **AC-3**.
* Exact manifest cleanup: Verifies cleanup removes only the specific IDs recorded in the invocation manifest and leaves all other database records intact, satisfies **AC-4**.
* Transaction failure and zero partial writes: Proves that failed run insertions, invalid event sequences, and oversized artifacts leave zero partial rows in the database, satisfies **AC-5**.
* Concurrent per run and global budget denial: Dispatches simultaneous parallel reservations exceeding per run caps and global 25 USD cap, verifying HTTP 409 rejection and zero budget overruns, satisfies **AC-6**.
* Deployment ordering and recovery: Validates secret provisioning before deployment, migration rollbacks, and Worker rollbacks, satisfies **AC-7**.

## Build plan

1. Fail closed Worker authentication update (`db-worker/src/index.ts`):
   Ensure `checkAuth` rejects requests immediately if `DB_BRIDGE_TOKEN` is unconfigured on remote environments, reserving local dummy token fallback for local dev server mode. Satisfies **AC-3**.

2. Backend isolation scoping (`backend/src/main.py`, `backend/src/worker.py`):
   Add configurable scoping to startup fixture sync, interrupted run recovery, and queue worker polling so that acceptance runs do not alter or claim unrelated tasks and runs. Satisfies **AC-2**.

3. Exact manifest remote acceptance suite (`backend/tests/test_k3_remote_d1.py`):
   Implement acceptance tests with `D1HostPorts` and fake adapters. Track all created IDs in an exact manifest. Verify fail closed auth, restart persistence, zero partial write assertions, concurrent per run budget denial, and global 25 USD cap denial. Delete only manifest records on cleanup. Satisfies **AC-2**, **AC-3**, **AC-4**, **AC-5**, **AC-6**.

4. Operator deployment and recovery guide (`docs/specs/0005-remote-cloudflare-d1-integration/verify.md`):
   Document exact step by step commands for preflight inspection, secret provisioning order, deployment, migration application, test execution, and rollback recovery. Satisfies **AC-1**, **AC-7**.

## Consequences

**Positive**:
* Guarantees remote acceptance tests run safely without corrupting, deleting, or failing unrelated database records.
* Eliminates security risks from unconfigured secrets by failing closed on remote edge infrastructure.
* Proves transactional integrity and budget safety under real network latency before introducing live model credentials in K4.

**Negative / tradeoffs**:
* Requires managing an explicit record manifest during test execution.
* Requires active Cloudflare account credentials and network connectivity during K3 acceptance runs.

**Neutral**:
* Local D1 development using `wrangler dev` remains fully supported for day to day offline work.

## Follow-up

- [ ] Run preflight verification script with operator credentials before applying remote migrations.
- [ ] Tag git repository with `checkpoint-k3-d1-integrated` after remote acceptance suite passes.

## Rationale

See [rationale.md](rationale.md) for background context, forces considered, and alternative architectural approaches.
