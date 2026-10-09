# RepoMedic — database reference

Owner B. Persistence via Cloudflare D1 through a private Worker bridge (the D1 bridge). Artifacts can be stored via the bridge or D1 compatible storage. No direct SQLite filesystem access, PostgreSQL, Redis or S3 for this MVP. The `REPOMEDIC_DB_WORKER_URL` environment variable configures the connection.

## Types and metadata

Opaque IDs and token hashes are TEXT. UTC times are ISO-8601 TEXT. Booleans are not needed in these tables. JSON is TEXT validated by shared Pydantic types at write/read boundaries. Cost columns are integer micro-USD (1 USD = 1,000,000); round reservations upward. API converts to displayed decimal dollars. Use Cloudflare D1 HTTP client behind repository functions; thread off blocking DB work from async routes. No ORM required.

## Schema

Notation: PK primary key, FK foreign key, NN not null. Every unnamed optional column below is nullable.

| Table | Columns and constraints |
| --- | --- |
| sessions | `token_hash TEXT PK`, `created_at TEXT NN`, `expires_at TEXT NN`; random session token hashed before storage |
| runs | `run_id TEXT PK`, `session_hash TEXT NN FK sessions.token_hash`, `task_id TEXT NN`, `mode TEXT NN`, `search_mode TEXT NN`, `state TEXT NN`, `reason TEXT`, `usage_json TEXT NN`, `created_at TEXT NN`, `updated_at TEXT NN`, `max_run_micro_usd INTEGER NN CHECK >=0` |
| events | `run_id TEXT NN FK runs.run_id`, `seq INTEGER NN CHECK >=1`, `ts TEXT NN`, `type TEXT NN`, `payload_json TEXT NN`; composite PK `(run_id,seq)` |
| artifacts | `artifact_id TEXT PK`, `run_id TEXT NN FK runs.run_id`, `kind TEXT NN`, `filename TEXT NN`, `storage_path TEXT NN`, `sha256 TEXT NN`, `size_bytes INTEGER NN CHECK >=0`, `created_at TEXT NN` |
| operations | `operation_id TEXT PK`, `run_id TEXT NN FK runs.run_id`, `kind TEXT NN`, `status TEXT NN`, `reserved_micro_usd INTEGER NN CHECK >=0`, `settled_micro_usd INTEGER CHECK >=0`, `provider_ref TEXT`, `created_at TEXT NN`, `updated_at TEXT NN` |

Enums use CHECK constraints matching API states/modes and artifact kinds. Operations kind is `model|sandbox`; status is `reserved|settled|uncertain|released`. Settled cost may be a conservative estimate if vendor billing is delayed; evidence labels it. Unknown paid completion stays uncertain with its reservation counted. Only an operation known not to have been submitted can release its reservation.

Indexes: runs(state,created_at); artifacts(run_id); operations(run_id,status). Tasks come from versioned curated recipe JSON, not a new editable tasks table. Candidate details live in durable events and evidence artifacts; do not create unnecessary candidate/user/team tables.

## Relationships

One session owns many runs. One run owns many events, artifacts and operations. Task ID references a versioned recipe in Git; evidence also records the recipe hash and commit so later edits cannot change historical meaning. Sessions are not hard-deleted on logout while referenced by runs; expire/revoke them and let retention purge runs first. Foreign keys restrict deletion; cleanup deletes dependent rows explicitly in a transaction.

## Transactions and state

Create a queued run atomically. Worker claims only queued rows. Allowed transitions: queued→running/failed/cancelled; running→succeeded/failed/cancelled. Terminal state is immutable. Conditional updates require the old active state, preventing a late engine result from overwriting cancellation. Final state and `run.finished` insert happen in one transaction, exactly once.

Allocate MAX(seq)+1 and insert under one short write transaction, or equivalent serialized allocation. Persist artifact metadata only after its bytes are safely written to a generated path inside the artifact root. No paths from users or model output. Reconcile unreferenced files after crashes; missing artifact bytes never imply repair success.

Budget reservation uses BEGIN IMMEDIATE, checking both run cap and global configured ceiling before insertion. Global committed cost = settled amount for settled operations + full reservations for reserved/uncertain operations. Include both model and sandbox operations. Settle once; overrun freezes further paid work and reports the breach rather than hiding it. Do not reset the ledger during development just to regain credits.

Worker restart marks running jobs failed with a restart reason; outstanding reservations become uncertain. Queued jobs may run once; no automatic resume of interrupted paid operations. No transaction stays open during network/provider calls.

## Lifecycle and verification

Initialize schema idempotently and track `PRAGMA user_version`; later incompatible changes require an explicit migration, never deleting the DB. Development tests use temporary directories. Startup does not erase records. Manual demo cleanup, after evidence backup, removes runs older than an operator-selected cutoff, then orphan files. Do not hard-code automatic retention before submission requirements are known.

Tests cover foreign keys, concurrent reservations, ordered events, terminal-state races, restart handling and cross-session isolation. API never serializes internal storage_path, provider_ref or token_hash.
