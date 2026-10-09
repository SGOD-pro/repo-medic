# Work package B: BACKEND

> For agentic workers: execute the linked feature specs task-by-task using Superpowers executing-plans inline. Read root/package AGENTS. No automatic subagent implementation/review loop.

Start gate: foundation F6 and common BASE_SHA. Develop independently; no dependency on another teammate running application.

Owned paths: `apps/api/`, its tests and `docs/progress/B.md`. Global schemas/config/migrations/fakes require foundation review. Do not build other owners modules to complete your local demo.

Read minimum: START_HERE, DECISIONS, CONTRACTS, TESTING, this document and current feature spec. Additional DATABASE/SECURITY/API relevant sections only. Historical v0.4 files are context, not current implementation commands.

Mock dependency: tests/support/FakeEngine and typed HostPorts; use real temporary SQLite. All fixtures are synthetic. Production integration must replace adapter at composition boundary without changing transport/domain contracts.

| Task | Build | Dependencies | Required acceptance identifier |
|---|---|---|---|
| [B1](../specs/B1.md) | SQLite repository and migration lifecycle | F6 | database_integrity |
| [B2](../specs/B2.md) | Session ownership and Origin security | B1 | session_ownership |
| [B3](../specs/B3.md) | Task admission and idempotency | B1,B2 | admission_idempotency |
| [B4](../specs/B4.md) | Host ports, budgets and artifacts | B1 | host_integrity |
| [B5](../specs/B5.md) | Worker lease, cancellation and recovery | B3,B4 | worker_recovery |
| [B6](../specs/B6.md) | SSE, summary and terminal atomicity | B4,B5 | event_reconnect |
| [B7](../specs/B7.md) | Replay metadata, readiness and handoff | B2,B6 | public_metadata |

## Working procedure

1. Check out feature/B-<task> from shared foundation; install committed locks.
2. Give agent prompts/B_START.md and current spec. Implement one task; do not ask it to build the whole product in a single prompt.
3. Write/run the named failing behavioral check, implement minimum change, run package checks plus canonical kit checks.
4. Record evidence in your ledger; fix failures through systematic debugging. No paid calls for A/B. C/D paid work only at explicit live gates with designated operator.
5. Handoff commit, tests/exits, fixture/mode/provenance and remaining limitations. Empty suites or screenshots aren't package acceptance.

## Definition of done

All owned task acceptance checks exist and pass, relevant build/typechecks pass, schemas match, no hidden other-package dependency, no copied/renamed shared fields, no fake result labeled live, no secrets. Only live tasks with actual recorded calls are live-complete. Standalone module readiness is distinct from integrated application readiness.

## Handoff command

`python tools/acceptance_gate.py --package B` intentionally refuses missing app/tests. A green command gate still requires all named acceptance cases and human review.
