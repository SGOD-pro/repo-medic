# Database Worker

## Overview

Private Cloudflare Worker bridge providing HTTP endpoints for Cloudflare D1 persistence. It enforces bearer token authorization, atomic sequence numbers, budget checks, and artifact limits without external cloud access during local development.

## Key files

| File | Owns |
|---|---|
| `src/index.ts` | Worker router and request handlers for runs, events, artifacts, and operations |
| `migrations/0001_initial_schema.sql` | Initial D1 SQL migration establishing schema and indexes |
| `wrangler.toml` | Worker configuration and D1 binding definition |
| `test_worker.mjs` | Test suite validating worker endpoints against local emulator |

## Commands

```bash
# Install dependencies
npm install

# Start local worker dev server
npm run dev

# Apply database migrations locally
npx wrangler d1 migrations apply repomedic-db --local

# Run worker test suite
node test_worker.mjs
```

## Conventions

* All endpoints except `/health` require `Authorization: Bearer <token>`
* Uses raw parameterized SQL with native D1 bindings without an ORM
* Atomic budget limits and sequence numbers are enforced directly in SQL

## Gotchas

* Event sequence numbers start at 1 and must be strictly gap free per run
* Operation settlements must not overwrite provider references on already settled entries

## Related specs

* [0001. Local D1 migrations and bridge](../docs/specs/0001-local-d1-migrations-and-bridge/index.md)
* [0005. Remote Cloudflare D1 integration](../docs/specs/0005-remote-cloudflare-d1-integration/index.md)

_Drafted by /audit from the repo, worth a quick human pass. Edit freely: once a line stops matching this draft, later runs treat it as curated and will flag rather than overwrite it._
