# RepoMedic — database reference

Owner B. Persistence uses Cloudflare D1 accessed through a private Cloudflare Worker bridge. No direct local SQLite filesystem access, PostgreSQL, Redis or S3 for this product. The environment variable REPOMEDIC_DB_WORKER_URL configures the private bridge connection. No user accounts, login, sessions, or session ownership exist in the database.

## Types and metadata

Opaque identifiers are TEXT. UTC timestamps are ISO 8601 strings. Booleans are stored as integers 0 or 1 if needed. JSON payloads are TEXT strings validated by shared Pydantic models at boundaries. Cost values are integer micro USD where 1 USD equals 1,000,000 micro USD. The public API converts these values to decimal numbers for display.

## Schema

Notation: PK is primary key, FK is foreign key, NN is not null. Every unnamed optional column is nullable.

| Table | Columns and constraints |
| --- | --- |
| runs | `run_id TEXT PK`, `task_id TEXT NN`, `mode TEXT NN`, `search_mode TEXT NN`, `state TEXT NN`, `reason TEXT`, `usage_json TEXT NN`, `created_at TEXT NN`, `updated_at TEXT NN`, `max_run_micro_usd INTEGER NN CHECK (max_run_micro_usd >= 0)` |
| events | `run_id TEXT NN FK runs.run_id`, `seq INTEGER NN CHECK (seq >= 1)`, `ts TEXT NN`, `type TEXT NN`, `payload_json TEXT NN`; composite PK `(run_id, seq)` |
| artifacts | `artifact_id TEXT PK`, `run_id TEXT NN FK runs.run_id`, `kind TEXT NN`, `filename TEXT NN`, `sha256 TEXT NN`, `size_bytes INTEGER NN CHECK (size_bytes >= 0)`, `content_base64 TEXT NN`, `created_at TEXT NN` |
| operations | `operation_id TEXT PK`, `run_id TEXT NN FK runs.run_id`, `kind TEXT NN`, `status TEXT NN`, `reserved_micro_usd INTEGER NN CHECK (reserved_micro_usd >= 0)`, `settled_micro_usd INTEGER CHECK (settled_micro_usd >= 0)`, `provider_ref TEXT`, `created_at TEXT NN`, `updated_at TEXT NN` |

Enum constraints match API values. Operation kinds are model or sandbox. Operation statuses are reserved, settled, uncertain, or released.

Indexes: runs(state, created_at); artifacts(run_id); operations(run_id, status).

## Artifact storage in D1

Artifacts are bounded and persisted directly inside Cloudflare D1 as base64 encoded text. Each individual artifact must not exceed 1,048,576 bytes (1 megabyte). Total artifact volume per run must not exceed 8,388,608 bytes (8 megabytes). Any attempt to exceed these boundaries fails clearly before storage.

## Private D1 Worker bridge contract

The Python backend communicates with Cloudflare D1 through HTTP endpoints on the private Worker bridge using authorization bearer token DB_BRIDGE_TOKEN.

### 1. Runs endpoints

- POST `/api/runs`: Create queued run.
  Request: `{"run_id": string, "task_id": string, "mode": string, "search_mode": string, "state": "queued", "max_run_micro_usd": number}`
  Response 201: `{"ok": true, "run_id": string}`

- GET `/api/runs/:run_id`: Fetch run details.
  Response 200: `{"run_id": string, "task_id": string, "mode": string, "search_mode": string, "state": string, "reason": string | null, "usage": object, "artifacts": array}`
  Response 404: `{"error": {"code": "not_found", "message": "Run not found"}}`

- PATCH `/api/runs/:run_id`: Transition state.
  Request: `{"state": string, "reason": string | null}`
  Response 200: `{"ok": true}`

### 2. Events endpoints

- POST `/api/runs/:run_id/events`: Append event.
  Request: `{"type": string, "payload": object}`
  Response 201: `{"ok": true, "seq": number, "ts": string}`

- GET `/api/runs/:run_id/events?after=0`: Fetch ordered events.
  Response 200: `{"events": [{"seq": number, "type": string, "payload": object, "ts": string}]}`

### 3. Artifacts endpoints

- POST `/api/runs/:run_id/artifacts`: Store bounded artifact.
  Request: `{"artifact_id": string, "kind": string, "filename": string, "sha256": string, "size_bytes": number, "content_base64": string}`
  Response 201: `{"ok": true, "artifact_id": string}`

- GET `/api/runs/:run_id/artifacts/:artifact_id`: Fetch artifact content.
  Response 200: `{"artifact_id": string, "kind": string, "filename": string, "sha256": string, "size_bytes": number, "content_base64": string}`
  Response 404: `{"error": {"code": "not_found", "message": "Artifact not found"}}`

### 4. Operations endpoints

- POST `/api/runs/:run_id/operations`: Reserve budget.
  Request: `{"operation_id": string, "kind": string, "reserved_micro_usd": number}`
  Response 201: `{"ok": true}`

- PATCH `/api/operations/:operation_id`: Settle actual cost.
  Request: `{"settled_micro_usd": number}`
  Response 200: `{"ok": true}`
