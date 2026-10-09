# A — frontend handoff

Read [shared rules](../AGENTS.md), [product](PRD.md), [architecture](ARCHITECTURE.md) and [build plan](PHASES.md). Start from `foundation-ready` on `feature/a-frontend`. You do not need the real backend to begin.

## Own and build

Own `frontend/src/app/`, UI components, `frontend/src/lib/api.ts` and `frontend/tests/`. Shared `contracts.ts`, root config and lockfiles are foundation-owned.

Build three small views: task selection, run progress, and result/evidence. Use one typed client with interchangeable mock/HTTP transports. Both expose the frozen API; components must not know which transport is active. Mock fixture mode is displayed clearly. No user accounts, access code login, or sessions.

Show mode, stage summaries, candidates, estimated cost, cancellation and final reason. Final results show source patch, verification evidence and owned download links. A failed run must not show a success banner; replay must say replay. Keep UI readable and responsive; no marketing pages, OAuth flows or unnecessary animation system.

Build order: task/result fixture screens → run start interactions → event reconnect/cancel → real HTTP integration. UI can list artifacts and download patch/evidence without adding an undocumented artifact-preview API.

## Acceptance checks

- Success, verification failure and cancellation fixtures all render truthful states.
- Typed start request uses exactly the frozen fields; keys and budget controls never enter browser bundles.
- Mock transport makes zero provider calls. HTTP transport uses `/api` directly with no session cookies or login.
- Duplicate/reconnected events are deduplicated by sequence; reading RunSummary recovers final state if SSE disconnects.
- Loading, empty tasks, and download errors have useful messages.
- Keyboard access and small screen layout work. Frontend build, lint, typecheck and focused interaction tests pass with the commands established in foundation.

Use `/develop`, `/check verify` and focused `/test`; `/debug` when a check fails. Request contract changes instead of inventing routes. Handoff your PR with real command results and screenshots; no paid testing required.
