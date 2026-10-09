# Shared contracts v0.5

Source: ../contracts/schema-source.json. Never manually alter generated schemas/types/OpenAPI. Foundation owner edits source, runs `python tools/generate_contracts.py`, updates fixtures, and runs all consumers' contract checks before merging. MVP consumers require exact `contract_version=0.5`.

All JSON keys are snake_case. IDs are opaque strings, times are UTC ISO 8601, nullable fields are explicitly present. Unknown properties rejected. Usage counts are nonnegative integers; boolean is not a count. USD values are six-decimal strings for Decimal arithmetic; missing/unconfirmed cost is null, not zero. Reasoning tokens may be null; document whether already included in billed output to avoid double counting.

## Interfaces

- A consumes HTTP/OpenAPI and EventEnvelope; rendering never constructs an engine result.
- B accepts CreateRunRequest, constructs EngineRequest + TaskRecipe, calls C through RepairEngine and implements HostPorts.
- C emits EngineEvent and returns EngineResult; host constructs/persists envelope. Engine doesn't choose seq/time/session or use SQL.
- D constructs the same EngineRequest and its own durable HostPorts implementation. It has no dependency on browser/API sessions.

B validates every incoming/outgoing boundary. A verifies fixture compatibility in tests and treats malformed stream payload as an error, not a new guessed state. C/D use canonical validation helpers before accepting result artifacts. JSON Schema structural checks alone do not implement verification; semantic gates are in validation.py and VERIFICATION.md.

## States

Run order: queued → provisioning → baseline_check → bump_check → diagnosing → searching → final_verification → succeeded. Error/cancel/budget states terminate from active stages. Unstable baseline / no breakage => aborted with explicit reason. Failed verification may return searching if the frozen policy still has budget; otherwise failed. Event sequence may contain multiple search/final-check cycles; don't hardcode one traversal.

Terminal states: succeeded, failed, aborted, cancelled, budget_exhausted. No new user-visible run events after committed run_terminal. Cleanup/audit logs are separate operational records. Cancellation/deadline/lease fencing wins over late success.

Branch states: planned, generating, patch_invalid, testing, partial, rejected, candidate, verifying, verified, winner, pruned. `candidate` is not verified success. branch_id identifies immutable node; refinement creates child with parent_id and incremented round, never overwrites parent history.

Event discriminated payloads: see schema-source EngineEvent/EventEnvelope. Envelope seq is per-run committed order; SSE `id` matches seq. Reconnect cursor is Last-Event-ID; client ignores duplicates <=last seen and fetches summary on a gap. Frozen full traces have contiguous seq and a terminal event. A partial live stream is not passed to validate_trace, which deliberately expects a complete frozen trace.

## Requests and results

Public POST runs accepts only task_id/search_mode. It does not accept repo_url, shell commands, API keys, budget, fake scenario, or mode. Server policy supplies these. Hidden developer fixture selection belongs to offline operator configuration, not a production request extension.

Success requires all verifier gates, nonempty intended suite, no failures, exit zero, correct winner and evidence. Failure has no winner; diagnostic artifacts may still be present. Model truncation is failure/ineligible patch. Retain raw provider status and authoritative test process evidence.

Versioned fixture names and fixture coverage list: MOCK_DATA.md. New shared fields require a contract change before consumers start depending on them; no duplicated aliases such as runId/run_id.
