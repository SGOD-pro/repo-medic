# RepoMedic — parallel work and checkpoints

We build one complete E2E app, split by layer. Three humans work concurrently in separate branches; no separate feature microservices. You are foundation/integration lead; you may also own B. If you own C instead, assign B to one teammate. Each builder gets the shared repo and one work package, not a different project.

## Assignments

| Person | Work package and owned output | Test dependency |
| --- | --- | --- |
| A | [Frontend](scope/frontend.md): task/progress/results/history, API client, UI checks | Fake HTTP responses; no DB or provider keys |
| B | [Backend](scope/backend.md): public API, D1 bridge/repositories/migrations, queue/HostPorts, artifact downloads | FakeEngine and local D1 emulator |
| C | [Engine](scope/engine.md): baseline/upgrade/repair/verifier, sequential and branch/refine, model/sandbox adapters | FakeHost and fake providers; no finished backend/UI |
| D optional | [Evaluation](scope/evaluation.md): regressions/evidence checker/benchmarks/demo | Starts with fixtures; real evaluation waits K4 |
| You/lead | Shared contracts/config/fixtures, PR review, checkpoint tags, merges and operator credentials | Coordinate; don't silently build others' owned paths |

## K0 — preparation before assigning implementation

You + C prepare the common base. Teammates may sketch UI or read provider docs, but do not invent API schemas or DB technology independently.

1. Put these 12 docs into the repo; archive conflicting old planning after review. PROJECT contains story only. AGENTS rules; PRD requirements/providers; architecture topology/internal ports; API public types; DATABASE D1 schema; UI screens; this file sequence/config.
2. Commit shared Pydantic `backend/src/contracts.py` and matching TS `frontend/src/lib/contracts.ts`, plus exact repair/HostPorts signatures and API fixtures. Validate JSON against both schemas.
3. Create canonical task recipe and success/failure/cancel/history/reconnect fixtures. Provider examples use sanitized/fake values; do not fabricate a real repository commit.
4. Create config parser and `.env.example` with network-free default, empty secrets, common environment names below. Commit lockfiles/tool versions (using `uv` for Python packages) and runnable build/lint/typecheck/test commands. Create FakeEngine, FakeHost and fake provider skeletons implementing shared interfaces; these need not implement production features.
5. Create db-worker skeleton/Wrangler config bound to your existing D1 ID; prepare local D1 emulator configuration. Freeze private bridge request/response contract from DATABASE. B implements repositories and migrations after this point, so the whole DB layer is not a prerequisite for teammates starting.
6. Check clean install and shared fixtures/fake-interface smoke tests. Tag `foundation-ready`. Give each builder their branch, package and exact acceptance command.

K0 exits only when the common base exists and its checks actually pass. Documentation alone is not this checkpoint. No provider keys or remote DB credentials are required for A/C offline work.

## K1 — A/B/C work in parallel

All branch from foundation-ready. Branches feature/a-frontend, feature/b-backend, feature/c-engine; D feature/d-evaluation if present. Root manifests/locks/shared types/config are lead-owned. Request dependency/interface changes through the lead rather than editing another package.

| Owner | Build order | Stop point / handoff |
| --- | --- | --- |
| A | Task screens → progress/results → history/reload → cancel/reconnect/errors; test mock transport | Stop declaring standalone work complete when all fixture checks + build/lint/typecheck pass. Submit PR; do not invent backend routes. After merge, switch to HTTP at K2. |
| B | Local D1 migrations/bridge → task/run/history API → FakeEngine queue → SSE/cancel/artifacts → budgets/restart | Stop declaring standalone work complete when API/local-D1 checks pass. Submit PR; do not rewrite C. Connect real engine at K2. |
| C | Provider fakes → baseline/upgrade → sequential → safe verifier/evidence → bounded branch/refine | Stop declaring standalone work complete when standalone fake harness/regressions pass. Submit PR; do not use paid keys yet. Real integration starts K2/K4. |
| D | Evidence schema checks, failure fixtures, evaluation runner and report format | Offline tools can begin now. Stop before claiming real measurements; wait K4 for paid evaluation. |

Each “stop” means stop at that boundary, submit the checked slice and work on another assigned offline check; it does not mean everyone must finish on the same day. Merge small compatible PRs continuously. An unfinished branch never changes frozen types privately.

## K2 — connect the real application, offline providers

Lead merges B and C, then B replaces FakeEngine with C's repair function and real HostPorts. A switches mock transport to actual public HTTP. Use local D1 emulator and fake model/sandbox. Everyone fixes their own component against the shared contracts.

K2 acceptance: start task from UI → persisted queued/running → repair stages/candidates → final result → downloadable patch/evidence → history/reload. Also run failure, cancellation, budget denial, unsafe patch, reconnect and backend restart. Both sequential and branch/refine must pass. No cloud-provider credits used.

If broken, integration stops at the failed scenario. Owner fixes it, adds regression and reruns offline before progressing. Lead tags offline-integrated only after checks pass.

## K3 — connect your real Cloudflare D1

You/B configure D1 binding/deploy bridge, apply reviewed migrations to the existing database and set backend bridge URL/token. Test create/read/event/cancel/history, transactional rollback, budget concurrency, chunk download hashes and persistence after application restart against remote D1. Use fake model/sandbox still. Remote D1 may consume Cloudflare plan quota but no model/sandbox credits.

K3 exits with D1-integrated tag and recorded remote DB checks. If D1 schema/bridge differs from local tests, add the failing scenario to regression coverage before proceeding. Do not replace D1 with a teammate's local database to hide failures.

## K4 — small actual provider verification and live E2E

You/C verify inference model/account/region, separate sandbox access/project credentials, SDK methods/images/costs and timeouts. Request sandbox beta access early in K0 so access delays do not surface here. A tiny operator-controlled discovery call may happen in parallel earlier; it does not make package tests paid or block K1.

Enable live explicitly for one task, sequential first. Observe original green→upgrade red→safe patch→fresh green and collect real evidence. Then verify branch/refine within caps. Same API/UI/DB/engine path as K2/K3; no separate live demo implementation.

On failure: preserve sanitized real request/response and logs → reproduce observed behavior in offline fixture/regression → fix → pass offline tests → operator runs only the failed real scenario with cap. Unknown paid completion stops retries; inspect provider operation first. Tag live-integrated only after actual live flow checks pass.

## K5 — evaluation, deployment and recording

D (or you) now evaluates real outcomes; A/B/C fix any regressions in their own paths. Compare one-shot, independent attempts, sequential and branch/refine with the same tasks/model/verifier and matched caps. Small samples are descriptive. Preserve failures and actual spend.

Deploy app + D1 bridge, verify origin/proxy, history/reload/download and mode restrictions, record complete user flow with real evidence. Public replay is labeled; local/private live app needs no account system. K5 completes the app only when all required PRD features work end to end. No “we will connect it later” remaining.

## Configure exactly these values

| Setting | Needed when / who sets it |
| --- | --- |
| REPOMEDIC_MODE=offline | K0 everyone; explicit live only operator K4; replay for public demo |
| REPOMEDIC_APP_ORIGIN | K0 local http://localhost:3000; actual deployed origin K5 |
| REPOMEDIC_DB_WORKER_URL | K0 local Worker URL; K3 deployed private bridge URL |
| REPOMEDIC_DB_WORKER_TOKEN | K0 local dummy service secret; K3 real service secret, backend only |
| DB_BRIDGE_TOKEN | Matching Worker secret; no browser exposure |
| Cloudflare account ID, existing D1 database_id, binding DB | K0 Wrangler skeleton; K3 deployment; not a postgres:// or sqlite:// URL |
| Cloudflare deployment API token | K3 owner/B only, least permissions for target deployment; not in app/browser |
| REPOMEDIC_MAX_RUN_USD | Operator positive cap before K4; absent rejects live startup |
| REPOMEDIC_TOTAL_BUDGET_USD=25 | Provisional overall model+sandbox allowance; replace with actual balance |
| REPOMEDIC_MAX_MODEL_CALLS | K0 cap 1 sequential; branch/refine explicitly reviewed <=6 calls (3 candidates, <=1 refinement each) |
| REPOMEDIC_MAX_OUTPUT_TOKENS=2048 | Provisional; K4 verify provider parameter/cost bound |
| REPOMEDIC_RUN_TIMEOUT_SECONDS=600 | Provisional full-run deadline; timeouts checked in all stages |
| REPOMEDIC_MAX_ARTIFACT_BYTES=1048576 | D1 bounded artifacts; per-run total 8388608, fail clearly if exceeded |
| TOKEN_FACTORY_API_KEY | K4 operator/C inference credential |
| TOKEN_FACTORY_BASE_URL / TOKEN_FACTORY_MODEL | K0 documented targets from PRD; account verified K4 |
| TOKEN_FACTORY_SANDBOX_BASE_URL | Documented sandbox target from PRD; verify K4 |
| TOKEN_FACTORY_SANDBOX_TOKEN / PROJECT_ID / IMAGE_ID | In app use full names TOKEN_FACTORY_SANDBOX_TOKEN, TOKEN_FACTORY_SANDBOX_PROJECT_ID, TOKEN_FACTORY_SANDBOX_IMAGE_ID; verify K4 |

Provider environment names are app-defined; adapters map into verified SDK constructors. A needs none of these secrets. B needs only local service-secret values until remote integration; C uses fakes until operator live work. No application user access-code or session config remains.

## Skills and credit discipline

Use [JS Mastery](https://github.com/jsmastery-pro/skills) as primary: /audit preserve rules; /scope complete supported app; /architect only missing shared decisions. Builders /develop one slice → /check verify → /test; /debug failures. Risky verifier/DB/interface PRs get /check review. /document writes actual PR results; /sync updates existing status. Optional [Superpowers](https://github.com/obra/superpowers) targeted TDD/debug; do not run both entire workflows or generate a new plan for every component. If IDE has no slash support, read/apply named SKILL.md.

Provisional $25 allocation: $2 discovery, $8 live integration, $5 evaluation, $10 recording/judge reserve. These are caps, not provider prices. Offline default even with keys present. No paid CI/on-save/on-PR checks, no automatic SDK paid retries. No workflow guarantees zero merge conflicts or zero model mistakes; shared contracts and regression checks make disagreements discoverable.
