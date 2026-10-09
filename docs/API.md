# API contract

Machine reference: ../contracts/openapi.json. Same-origin cookie `repomedic_session`; no provider keys in request bodies/URLs. B normalizes framework validation errors to ErrorResponse.

| Method/path | Response | Access |
|---|---|---|
| POST /api/session | 200 SessionResponse + cookie | Rate-limited code exchange |
| DELETE /api/session | 204 | Current session, revoke + clear cookie |
| GET /api/tasks | 200 array TaskSummary | Public curated metadata |
| POST /api/runs | 202 CreateRunResponse | Session; required Idempotency-Key |
| GET /api/runs/{run_id} | 200 RunSummary | Owner only |
| GET /api/runs/{run_id}/events | 200 text/event-stream | Owner only; Last-Event-ID |
| POST /api/runs/{run_id}/cancel | 202 {run_id,cancel_requested:true} | Owner; idempotent |
| GET /api/runs/{run_id}/artifacts/{artifact_id} | 200 bytes | Owner; safe artifact-ID lookup |
| GET /api/replays | 200 array ReplaySummary | Public intentionally published records |
| GET /api/eval/summary | 200 EvalSummary | Public frozen methodology/results |
| GET /api/health | 200 {status,contract_version} | Minimal readiness; unavailable can be 503 |

401 expired/invalid session; 404 absent or nonowned run/artifact; 409 reused idempotency key with different canonical payload hash; 422 invalid fields/task/mode policy; 429 code throttle/admission quota; 503 unavailable provider/storage. Origin rejection is 403 invalid_request. Generic OpenAPI error entries describe common envelope, not every possible status on every endpoint.

Same session + same idempotency key/payload returns the original CreateRunResponse even if the run has progressed; state in that admission response remains queued. Fetch summary for current state. Different sessions can independently use the same key. Double-click in UI reuses admission key; new attempt generates new key.

SSE data is JSON EventEnvelope; event id is seq. On terminal flush committed event then close connection. On reconnect emit persisted rows after cursor; invalid/future cursor => 422. Heartbeats are comments (not persisted events). Disconnect doesn't cancel a run. Don't store sensitive keys/code in event/log content.

Downloads use Content-Disposition with sanitized filename and hash metadata. Path from browser never maps directly to disk. A accepts MIME-specific file bytes; JSON errors must never become a misleading downloaded patch.

Replay details are static intentionally public assets generated at release under apps/web/public/replays/{replay_id}/events.json and result.json; metadata is GET /api/replays. These don't call the live start endpoint. Never expose a private live artifact via an guessed replay ID.
