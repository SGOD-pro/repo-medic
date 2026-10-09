# B — backend handoff

Read [shared rules](../AGENTS.md), [product](PRD.md), [architecture](ARCHITECTURE.md) and [build plan](phases.md). Start from `foundation-ready` on `feature/b-backend`. Use FakeEngine until C is ready.

## Own and build

Own `backend/src/api/`, `backend/src/storage/`, `backend/src/worker.py`, backend application entrypoint and `backend/tests/api/`. Do not change engine code or shared contracts independently.

Implement the frozen routes, access-code session and ownership checks; persist runs, ordered events and artifacts in one SQLite database. One worker handles queued runs and calls the shared engine function. Implement HostPorts for event persistence, artifact writes, cancellation and atomic budget reservation/settlement. Keep database transactions short; never hold one while waiting for a provider.

FakeEngine implements the same function as C and emits the shared fixtures. It is test support, not a second API. B owns final state transitions and final events. Reject late success after cancellation. On restart, mark interrupted runs failed and retain uncertain spend reservations; do not resubmit paid work.

Build order: session + tasks → run storage/FakeEngine → SSE/cancel/download → budget and restart behavior → import C's engine → full offline integration.

## Acceptance checks

- Session creation/revocation/expiry work; unauthenticated and cross-session run/artifact access is rejected.
- Mutation origin checks work in deployment configuration; provider secrets never appear in responses or logs.
- Start persists a queued run and returns 202. Polling/SSE agree, ordered reconnect works, duplicate cancellation is safe.
- Artifact IDs resolve only owned allowlisted files; traversal and symlink escape are blocked.
- Budget reservations cannot exceed per-run or global caps; an unknown paid outcome is not automatically retried or refunded.
- Terminal states cannot change to success later. Restart does not lose events or accidentally repeat paid calls.
- API tests use temporary SQLite/artifact directories and FakeEngine, never keys.

Use `/develop`, `/test`, `/debug`, `/check verify`; review security/state transitions before merge. Report passing commands and remaining limitations. B's merge does not depend on C being finished; live acceptance waits for C integration.
