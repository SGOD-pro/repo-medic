# 0001. Local D1 migrations and bridge: rationale

## Context

RepoMedic requires durable persistence for task runs, chronological event streams, bounded artifact files, and budget reservations. Our architecture document assigns all persistence to Cloudflare D1 accessed through a private Worker bridge. Direct access to a local SQLite file, PostgreSQL, Redis, or object storage is prohibited by project guidelines. The backend must communicate with D1 strictly through HTTP endpoints hosted on the Worker bridge.

Package B owns the backend storage layer, the Worker code, and database migrations. While early setup provided a basic Worker skeleton and partial Python client, the actual database schema migration, endpoint handlers, atomic constraints, and error envelopes are not yet implemented. Without this local bridge, the backend cannot persist runs or emit durable events during offline development.

The operational reality demands a completely offline workflow during early development phases. Tests and local runs must execute against the local D1 emulator provided by Wrangler. We need strict boundary validation in the Worker to prevent budget overruns, reject oversized artifacts, and guarantee that completed runs cannot be reopened.

## Options considered

### Option 1: Native TypeScript Worker router with raw SQL queries (Recommended)

Build the private bridge using standard Web standard Request and Response primitives inside `db-worker/src/index.ts`. All database operations execute raw SQL statements directly on the D1 database binding (`env.DB`).

**Pros**:
* Introduces zero new npm dependencies beyond the existing Wrangler setup.
* Keeps the code small, clear, and easy to audit for atomic checks.
* Preserves full control over SQL transactions and constraint checks.

**Cons**:
* Requires manual URL pattern matching and request body parsing in the Worker.

### Option 2: Framework router such as Hono with Drizzle ORM

Use an external lightweight framework router and an object relational mapping library inside the Worker.

**Pros**:
* Provides automatic route matching and typed SQL helpers.

**Cons**:
* Adds external dependencies to `package.json`, which violates team rules reserving dependency lock changes for the lead.
* Increases build complexity and bundle size for a private bridge that only needs nine simple endpoints.

### Option 3: Local SQLite file bypass for Python tests

Allow the Python backend to connect directly to a local SQLite file during local testing, reserving the Worker bridge for production deployments.

**Pros**:
* Skips running the Node Worker process during Python unit tests.

**Cons**:
* Violates project architectural constraints in `docs/DATABASE.md`.
* Hides Worker bridge bugs and serialization discrepancies until remote deployment.
* Prevents testing Worker authentication and validation logic offline.

## Rationale

Option 1 provides the simplest possible solution that fulfills all architectural constraints. The existing `db-worker/package.json` already contains Wrangler. Introducing additional libraries would require modifying shared lock files that remain lead owned. Raw SQL queries give us precise control over atomic sequence number generation, budget sum calculations, and terminal state immutability checks.

Option 2 introduces unnecessary abstraction for nine private endpoints. Option 3 creates an unverified architectural divergence that contradicts our offline first acceptance goals. Running the actual Worker against the local D1 emulator gives us high confidence that behavior in development matches production deployment.

## Consequences

**Positive**:
* Enables complete offline development for Package B without needing cloud access or paid tokens.
* Enforces data integrity, budget caps, and storage limits directly at the database boundary.
* Keeps the Worker codebase simple and free from third party framework bloat.
* Provides clear parity with the planned production Cloudflare D1 environment.

**Negative (tradeoffs)**:
* Requires running the local Wrangler dev process during integration testing.
* Raw SQL queries inside the Worker must be carefully maintained as schema evolves.

**Neutral**:
* The lead owner must be notified to align the token configuration variable in `backend/src/config.py` (`db_bridge_token` versus `repomedic_db_worker_token`).
