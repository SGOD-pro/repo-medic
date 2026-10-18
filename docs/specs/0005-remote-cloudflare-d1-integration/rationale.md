# Rationale: Remote Cloudflare D1 integration

## Context

In checkpoint K2, we verified the complete integration of our Python backend, real repair engine, and Next.js frontend against a local Cloudflare D1 emulator running on port 8787. All local scenarios passed offline, including background process termination, startup recovery, stream interruption, budget denials, and sequential and branch refine runs.

Checkpoint K3 requires proving that the same persistence architecture functions reliably against a real remote Cloudflare D1 database instance. Moving from a local emulator to remote Cloudflare D1 introduces critical operational and architectural requirements:

First, remote acceptance testing must never alter, claim, or delete unrelated tasks and runs. The backend startup lifecycle includes task fixture synchronization, recovery of interrupted runs left in a running state, and worker queue polling. In a shared or remote environment, uncontrolled startup recovery would inadvertently mark legitimate running tasks as failed, fixture synchronization could overwrite curated tasks, and queue workers could consume unrelated jobs. Acceptance execution requires dedicated database isolation or enforceable namespace scoping across every affected backend path.

Second, test record cleanup must be exact. Broad pattern matching queries (such as SQL `LIKE` deletions) risk destroying concurrent test runs or unrelated data. The test runner must maintain an exact manifest of every entity created during an invocation (tasks, runs, operations, artifacts) and delete only those specific primary keys.

Third, edge authentication must fail closed. If the secret bridge token is unconfigured on the remote Worker, the service must immediately reject requests rather than silently falling back to local development dummy tokens. Safe deployment requires a strict ordering: provisioning secrets before deploying code or routing traffic.

Fourth, remote testing must prove that atomic operations and budget limits hold under real network latency. This includes verifying zero partial writes on failed transactions, atomic enforcement of per run spending caps, and atomic enforcement of the global 25 USD budget cap across concurrent branches using `D1HostPorts`.

## Options considered

### Option 1: Direct Cloudflare Worker bridge deployment with fail closed authentication, scoped backend isolation, and exact manifest cleanup (Chosen)

Deploy the existing TypeScript Worker directly to Cloudflare edge infrastructure using Wrangler. The Worker binds natively to the Cloudflare D1 database and exposes the private HTTP contract defined in `docs/DATABASE.md`. Access is guarded by `DB_BRIDGE_TOKEN` bearer authentication that fails closed if the secret is unconfigured. The Python backend communicates with the bridge over HTTPS via `D1HostPorts`. Acceptance testing operates on a dedicated acceptance database or strictly scoped task and run namespaces with exact manifest cleanup.

**Pros**:
* Maintains exact architectural symmetry between local development and remote deployment.
* Reuses existing TypeScript routes, parameterized SQL queries, and validation logic without code duplication.
* Encapsulates raw SQL execution inside the Cloudflare edge network, requiring no external database drivers in Python.
* Guarantees that unconfigured secrets immediately block access rather than leaving a security loophole.
* Protects unrelated database records from accidental corruption or deletion during acceptance runs.
* Validates concurrent budget reservation and rollback behavior under real network latency.

**Cons**:
* Adds network latency between the Python backend and Cloudflare edge Worker.
* Requires managing Worker deployment lifecycle and secret provisioning alongside database migrations.

### Option 2: Cloudflare D1 REST API called directly from Python backend

Bypass the custom Worker bridge and have the Python backend call Cloudflare's public Cloudflare API endpoint for D1 (`https://api.cloudflare.com/client/v4/accounts/<account>/d1/database/<db>/query`).

**Pros**:
* Eliminates the need to deploy and maintain a custom Worker bridge script.

**Cons**:
* Cloudflare public API requires global API tokens or User API tokens with broad account level permissions, increasing blast radius.
* Lacks custom edge logic for enforcing atomic monotonic event sequence numbers, payload size limits, and custom 409 conflict errors.
* Slower response times due to API gateway overhead compared to edge Worker execution.
* Breaks symmetry with our local development environment which relies on `db-worker`.

### Option 3: Remote SQLite tunneling or external relational database

Replace Cloudflare D1 with an external PostgreSQL or SQLite over SSH tunnel during testing.

**Pros**:
* Familiar tooling and direct database driver connections.

**Cons**:
* Violates core PRD and architecture requirements mandating Cloudflare D1.
* Fails to validate Cloudflare D1 edge characteristics, defeating the purpose of checkpoint K3.

## Rationale

Option 1 is selected because it strictly preserves the architecture validated in checkpoints K1 and K2 while resolving all operational hazards of remote edge deployment:
1. Strict bearer token authentication that fails closed on remote deployments if secrets are omitted.
2. Complete isolation of acceptance runs through dedicated database bindings or explicit namespace scoping across startup sync, recovery, and queue polling.
3. Clean, surgical deletion restricted to an exact invocation manifest of created IDs, preventing data loss in shared environments.
4. Native D1 SQL atomicity enforcing monotonic event sequences, payload volume limits, and concurrent per run and global budget caps.

By deploying this bridge to Cloudflare, provisioning secrets before routing traffic, and using `D1HostPorts` with fake model adapters, the backend storage repositories continue working with zero code modifications while providing ironclad isolation and safety guarantees.

## References

* Cloudflare D1 Documentation: Developer guides and client API specifications for distributed SQLite on Cloudflare edge.
* Cloudflare Wrangler CLI Reference: Deployment commands, migration management, and secret provisioning.
* Project Architecture Reference: `docs/DATABASE.md` and `docs/PHASES.md` defining private bridge contract and checkpoint sequencing.
