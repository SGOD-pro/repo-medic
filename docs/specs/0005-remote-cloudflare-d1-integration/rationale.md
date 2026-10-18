# Rationale: Remote Cloudflare D1 integration

## Context

In checkpoint K2, we verified the complete integration of our Python backend, real repair engine, and Next.js frontend against a local Cloudflare D1 emulator running on port 8787. All local scenarios passed offline, including background process termination, startup recovery, stream interruption, budget denials, and sequential and branch refine runs.

Checkpoint K3 requires proving that the same persistence architecture functions reliably against a real remote Cloudflare D1 database instance. Cloudflare D1 is built on SQLite distributed over Cloudflare edge infrastructure. While local emulator development mimics basic SQL behavior, remote D1 introduces edge routing, network latency, strict transactional boundaries, remote migration ledgers, and distinct error responses.

We must connect to real Cloudflare D1 without compromising the safety boundaries established in K0 through K2. In particular, we must prevent test records from accumulating as permanent database bloat, guarantee that migrations do not conflict with existing tables, protect private bridge tokens from browser exposure, and maintain offline provider fakes so zero paid model or sandbox API credits are consumed.

## Options considered

### Option 1: Direct Cloudflare Worker bridge deployment with backend service token (Chosen)

Deploy the existing TypeScript Worker directly to Cloudflare edge infrastructure using Wrangler. The Worker binds natively to the Cloudflare D1 database and exposes the private HTTP contract defined in `docs/DATABASE.md`. Access is guarded by `DB_BRIDGE_TOKEN` bearer authentication. The Python backend communicates with the bridge over HTTPS.

**Pros**:
* Maintains exact architectural symmetry between local development and remote deployment.
* Reuses existing TypeScript routes, parameterized SQL queries, and validation logic without code duplication.
* Encapsulates raw SQL execution inside the Cloudflare edge network, requiring no external database drivers in Python.
* Keeps the Next.js frontend completely decoupled from database credentials and topology.

**Cons**:
* Adds a network hop between the Python backend and Cloudflare edge Worker.
* Requires managing Worker deployment lifecycle alongside database migrations.

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

Option 1 is selected because it strictly preserves the architecture validated in checkpoints K1 and K2. The private Worker bridge serves as an explicit data access layer that enforces application rules directly at the edge:
1. Strict bearer token authentication protecting database access.
2. Atomic sequence generation for event streaming.
3. Hard boundaries on individual artifact size (1 megabyte) and run artifact volume (8 megabytes).
4. Atomic budget reservation and settlement checks preventing concurrent race conditions.

By deploying this bridge to Cloudflare and pointing our backend `REPOMEDIC_DB_WORKER_URL` to its HTTPS endpoint, the backend storage repositories continue working with zero code modifications.

## References

* Cloudflare D1 Documentation: Developer guides and client API specifications for distributed SQLite on Cloudflare edge.
* Cloudflare Wrangler CLI Reference: Deployment commands, migration management, and secret provisioning.
* Project Architecture Reference: `docs/DATABASE.md` and `docs/PHASES.md` defining private bridge contract and checkpoint sequencing.
