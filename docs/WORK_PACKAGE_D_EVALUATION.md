# Work package D: EVALUATION

> For agentic workers: execute the linked feature specs task-by-task using Superpowers executing-plans inline. Read root/package AGENTS. No automatic subagent implementation/review loop.

Start gate: foundation F6 and common BASE_SHA. Tooling D1–D3 starts immediately; real D4 waits for integrated live engine.

Owned paths: `packages/evaluation/`, its tests and `docs/progress/D.md`. Global schemas/config/migrations/fakes require foundation review. Do not build other owners modules to complete your local demo.

Read minimum: START_HERE, DECISIONS, CONTRACTS, TESTING, this document and current feature spec. Additional EVALUATION/BUDGET/MOCK_DATA relevant sections only. Historical v0.4 files are context, not current implementation commands.

Mock dependency: FakeEngine/results and own experiment HostPorts; reuse stable host library if supplied. All fixtures are synthetic. Production integration must replace adapter at composition boundary without changing transport/domain contracts.

| Task | Build | Dependencies | Required acceptance identifier |
|---|---|---|---|
| [D1](../specs/D1.md) | Task/config manifests and fake runner | F6 | runner_contract |
| [D2](../specs/D2.md) | Durable experiment host and raw evidence | D1 | raw_attempt_retention |
| [D3](../specs/D3.md) | Metrics and comparative accounting | D1,D2 | metric_denominators |
| [D4](../specs/D4.md) | Bounded real evaluation | I4,C7,D3 | live_eval_provenance |
| [D5](../specs/D5.md) | Failure regression and publishable evidence | D4 | failure_to_regression |

## Working procedure

1. Check out feature/D-<task> from shared foundation; install committed locks.
2. Give agent prompts/D_START.md and current spec. Implement one task; do not ask it to build the whole product in a single prompt.
3. Write/run the named failing behavioral check, implement minimum change, run package checks plus canonical kit checks.
4. Record evidence in your ledger; fix failures through systematic debugging. No paid calls for A/B. C/D paid work only at explicit live gates with designated operator.
5. Handoff commit, tests/exits, fixture/mode/provenance and remaining limitations. Empty suites or screenshots aren't package acceptance.

## Definition of done

All owned task acceptance checks exist and pass, relevant build/typechecks pass, schemas match, no hidden other-package dependency, no copied/renamed shared fields, no fake result labeled live, no secrets. Only live tasks with actual recorded calls are live-complete. Standalone module readiness is distinct from integrated application readiness.

## Handoff command

`python tools/acceptance_gate.py --package D` intentionally refuses missing app/tests. A green command gate still requires all named acceptance cases and human review.
