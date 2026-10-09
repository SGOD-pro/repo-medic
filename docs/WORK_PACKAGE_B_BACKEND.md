# B — backend handoff

Read [shared rules](../AGENTS.md), [product](PRD.md), [architecture](ARCHITECTURE.md) and [build plan](PHASES.md). Start from `foundation-ready` on `feature/b-backend`. Use FakeEngine until C is ready.

## Own and build

Own `backend/src/api/`, `backend/src/storage/`, `backend/src/worker.py`, backend application entrypoint and `backend/tests/api/`. Do not change engine code or shared contracts independently.

Implement the frozen routes without user sessions or access codes; persist runs, ordered events and artifacts via Cloudflare D1 through the private Worker bridge. One worker handles queued runs and calls the shared engine function. Implement HostPorts for event persistence, artifact writes, cancellation and atomic budget reservation/settlement. Keep bridge calls short; never hold one while waiting for a provider.

FakeEngine implements the same function as C and emits the shared fixtures. It is test support, not a second API. B owns final state transitions and final events. Reject late success after cancellation. On restart, mark interrupted runs failed and retain uncertain spend reservations; do not resubmit paid work.

Build order: tasks → run storage/FakeEngine → SSE/cancel/download → budget and restart behavior → import C's engine → full offline integration.

## Acceptance checks

- Routes reject invalid requests and enforce offline first constraints; no user account or login logic.
- Mutation origin checks work in deployment configuration; provider secrets never appear in responses or logs.
- Start persists a queued run in D1 and returns 202. Polling/SSE agree, ordered reconnect works, duplicate cancellation is safe.
- Artifact IDs resolve only valid allowlisted files; traversal and symlink escape are blocked.
- Budget reservations cannot exceed per-run or global caps; an unknown paid outcome is not automatically retried or refunded.
- Terminal states cannot change to success later. Restart does not lose events or accidentally repeat paid calls.
- API tests use local D1 emulator/bridge and FakeEngine, never keys.

Use `/develop`, `/test`, `/debug`, `/check verify`; review security/state transitions before merge. Report passing commands and remaining limitations. B's merge does not depend on C being finished; live acceptance waits for C integration.
