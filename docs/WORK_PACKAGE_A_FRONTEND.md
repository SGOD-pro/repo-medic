# Work package A: FRONTEND

> For agentic workers: execute the linked feature specs task-by-task using Superpowers executing-plans inline. Read root/package AGENTS. No automatic subagent implementation/review loop.

Start gate: foundation F6 and common BASE_SHA. Develop independently; no dependency on another teammate running application.

Owned paths: `apps/web/`, its tests and `docs/progress/A.md`. Global schemas/config/migrations/fakes require foundation review. Do not build other owners modules to complete your local demo.

Read minimum: START_HERE, DECISIONS, CONTRACTS, TESTING, this document and current feature spec. Additional UI_UX/design/API relevant sections only. Historical v0.4 files are context, not current implementation commands.

Mock dependency: fixtures/api/ and fixtures/scenarios/; implement dev mock client with generated types. All fixtures are synthetic. Production integration must replace adapter at composition boundary without changing transport/domain contracts.

| Task | Build | Dependencies | Required acceptance identifier |
|---|---|---|---|
| [A1](../specs/A1.md) | Typed API client and fixture switch | F6 | api_client_contract |
| [A2](../specs/A2.md) | Task selection and access-code flow | A1 | session_start_flow |
| [A3](../specs/A3.md) | Run reducer and SSE recovery | A1 | sse_recovery |
| [A4](../specs/A4.md) | Branch and verification evidence view | A3 | evidence_rendering |
| [A5](../specs/A5.md) | Cancel and safe artifact download | A2,A3 | cancel_download_flow |
| [A6](../specs/A6.md) | Replay, evaluation, accessibility and handoff | A4,A5 | replay_never_starts_live |

## Working procedure

1. Check out feature/A-<task> from shared foundation; install committed locks.
2. Give agent prompts/A_START.md and current spec. Implement one task; do not ask it to build the whole product in a single prompt.
3. Write/run the named failing behavioral check, implement minimum change, run package checks plus canonical kit checks.
4. Record evidence in your ledger; fix failures through systematic debugging. No paid calls for A/B. C/D paid work only at explicit live gates with designated operator.
5. Handoff commit, tests/exits, fixture/mode/provenance and remaining limitations. Empty suites or screenshots aren't package acceptance.

## Definition of done

All owned task acceptance checks exist and pass, relevant build/typechecks pass, schemas match, no hidden other-package dependency, no copied/renamed shared fields, no fake result labeled live, no secrets. Only live tasks with actual recorded calls are live-complete. Standalone module readiness is distinct from integrated application readiness.

## Handoff command

`python tools/acceptance_gate.py --package A` intentionally refuses missing app/tests. A green command gate still requires all named acceptance cases and human review.
