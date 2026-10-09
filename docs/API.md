# RepoMedic — application API

Owner B; A consumes these routes; foundation owns matching Pydantic/TypeScript types. This is a design contract, not tested OpenAPI output. API requests use same-origin `/api`; development needs a local proxy so cookies and SSE follow the same contract.

## Headers and session

JSON requests: `Content-Type: application/json`, `Accept: application/json`. Browser client sends session cookie with credentials; no application bearer token, API key or provider token goes in browser requests. Server checks the Origin on mutations against its configured application origin. GET SSE uses `Accept: text/event-stream`; reconnect may send Last-Event-ID. Native EventSource cannot set arbitrary request headers, so cookie authentication is intentional.

POST session returns `Set-Cookie: repomedic_session=<opaque random token>; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=<configured TTL>`. Development may omit Secure only on localhost. Session tokens never appear in response JSON. Login rate limiting is required. Expired/revoked sessions receive 401; ownership mismatches receive 404 to avoid leaking run existence.

## Routes and shared data structures


All routes use `/api`. Session required except creating a session. Every run and artifact access checks session ownership. Errors: `{error:{code:string,message:string}}`. POST JSON rejects unknown fields. Run/task/artifact IDs are opaque server-issued strings, never filesystem paths.

| Method/path | Input or output |
| --- | --- |
| POST `/session` | `{access_code:string}` → `{authenticated:true}` and session cookie |
| DELETE `/session` | Clear/revoke session; 204 |
| GET `/tasks` | `{tasks:TaskSummary[]}` |
| POST `/runs` | `{task_id:string,search_mode:"sequential"|"branch_refine"}` → RunSummary; 202 |
| GET `/runs/{id}` | RunSummary |
| GET `/runs/{id}/events?after=0` | SSE; replay durable events whose seq exceeds `after`, then stream |
| POST `/runs/{id}/cancel` | `{}` → RunSummary; idempotent |
| GET `/runs/{id}/artifacts/{artifact_id}` | Owned, allowlisted file download |

`TaskSummary={task_id,title,repository_url,commit_sha,dependency,from_version,to_version}`: all strings.

`RunSummary={run_id,task_id,mode,search_mode,state,reason,usage,artifacts}`. `mode` is `offline|replay|live`; server chooses it. `state` is `queued|running|succeeded|failed|cancelled`. `reason` is string or null. `usage={model_calls:int,input_tokens:int,output_tokens:int,estimated_usd:number}`; values are nonnegative, estimates explicitly labeled. `artifacts` is an array of `{artifact_id:string,kind:"patch"|"evidence"|"log",filename:string}`. The chosen run cost cap is included in the initial event.

SSE sends `id: seq`, `event: type`, and JSON data `{run_id,seq,ts,type,payload}`. `seq` starts at 1; `ts` is UTC ISO-8601. Types: `run.started`, `stage.completed`, `candidate.completed`, `usage.updated`, `run.finished`. Payloads respectively: `{mode,search_mode,max_run_usd}`, `{stage:"baseline"|"upgrade"|"repair"|"verification",passed:boolean,summary:string}`, `{candidate_id,passed:boolean,summary:string}`, Usage, and `{state,reason}`. Reconnect uses the larger of query `after` and valid Last-Event-ID. Frontend also reads RunSummary so a missed stream never hides completion.


All timestamps are UTC. JSON property names are snake_case. Public summaries exclude provider refs, private filesystem paths, and secrets. Floats in usage are display estimates; backend cost accounting uses integer micro-USD (see DATABASE).

## Endpoint behavior and errors

| Route | Behavior and statuses |
| --- | --- |
| POST `/api/session` | 200 valid code; 401 wrong code; 422 invalid shape; 429 rate limited |
| DELETE `/api/session` | 204, revoke if present; safe to repeat |
| GET `/api/tasks` | 200 curated task metadata; 401 unauthenticated |
| POST `/api/runs` | 202 persists queue entry; 404 unknown task; 409 mode disabled/budget unavailable; 422 invalid search mode/fields |
| GET `/api/runs/{id}` | 200 owned summary; 404 missing/unowned |
| GET `/api/runs/{id}/events` | 200 event stream; validate ownership before headers; 422 invalid/negative cursor |
| POST `/api/runs/{id}/cancel` | 200 marks queued/running cancelled; terminal run returns unchanged summary |
| GET artifact | 200 binary/text with Content-Disposition attachment and correct Content-Type; 404 absent/unowned |

Common 503 means backend unavailable; 500 is a sanitized internal error. FastAPI validation errors must be translated into the common error envelope. Proposed stable codes: `unauthenticated`, `invalid_access_code`, `rate_limited`, `not_found`, `invalid_request`, `mode_disabled`, `budget_exhausted`, `internal_error`, `unavailable`. Never return stack traces. A run failing verification is a 200 summary with state failed, not a transport error.

POST run is not automatically retried after an uncertain response: it could already have created a paid run. Frontend tells the user the outcome is uncertain; operator checks durable records. Request idempotency can be added later only through a shared contract change.

## Concrete request/response

```http
POST /api/runs
Content-Type: application/json
Origin: https://<configured-app-origin>
Cookie: repomedic_session=<opaque-token>

{"task_id":"upgrade-example-01","search_mode":"sequential"}
```

```json
{
  "run_id":"run_example_01",
  "task_id":"upgrade-example-01",
  "mode":"offline",
  "search_mode":"sequential",
  "state":"queued",
  "reason":null,
  "usage":{"model_calls":0,"input_tokens":0,"output_tokens":0,"estimated_usd":0},
  "artifacts":[]
}
```

These identifiers are illustrative, not actual curated repository data. Error example: `{"error":{"code":"budget_exhausted","message":"The configured budget is unavailable."}}`.

## SSE lifecycle

Heartbeat comments roughly every 15 seconds, never persisted as events. Persist each meaningful event before publishing. Reconnect replays the cursor range in ascending order, then tails new records without a gap. A terminal stream sends remaining events then closes. A fetches RunSummary on reconnect/disconnect and deduplicates sequences. `run.finished` payload state is restricted to succeeded/failed/cancelled. Usage events report cumulative values.

OpenAPI is generated from the shared Pydantic types once implemented. Foundation supplies success/failure/cancel fixtures valid against those types. A and B must pass the same fixture/schema checks before HTTP integration.
