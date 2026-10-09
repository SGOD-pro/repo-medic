# Work package C: ENGINE

> For agentic workers: execute the linked feature specs task-by-task using Superpowers executing-plans inline. Read root/package AGENTS. No automatic subagent implementation/review loop.

Start gate: foundation F6 and common BASE_SHA. Develop independently; no dependency on another teammate running application.

Owned paths: `packages/repair/`, its tests and `docs/progress/C.md`. Global schemas/config/migrations/fakes require foundation review. Do not build other owners modules to complete your local demo.

Read minimum: START_HERE, DECISIONS, CONTRACTS, TESTING, this document and current feature spec. Additional VERIFICATION/CONFIG/BUDGET relevant sections only. Historical v0.4 files are context, not current implementation commands.

Mock dependency: ScriptedModel/ScriptedSandbox plus MemoryHost or richer owned host harness; trusted compat fixture. All fixtures are synthetic. Production integration must replace adapter at composition boundary without changing transport/domain contracts.

| Task | Build | Dependencies | Required acceptance identifier |
|---|---|---|---|
| [C1](../specs/C1.md) | Standalone engine composition and ports | F6 | engine_ports |
| [C2](../specs/C2.md) | Recipe preparation and baseline/bump checks | C1 | baseline_bump_policy |
| [C3](../specs/C3.md) | Diagnosis, focused context and patch validation | C1,C2 | patch_policy |
| [C4](../specs/C4.md) | Sequential repair with bounded feedback | C2,C3 | sequential_budget |
| [C5](../specs/C5.md) | Fresh final verification and selection | C3,C4 | hard_verifier_gates |
| [C6](../specs/C6.md) | Real Token Factory adapters and smoke repair | F5,C1,C5 | live_adapter_no_fallback |
| [C7](../specs/C7.md) | Independent and branch/refine policies | C4,C5 offline; C6/I4 live | branch_isolation |

## Working procedure

1. Check out feature/C-<task> from shared foundation; install committed locks.
2. Give agent prompts/C_START.md and current spec. Implement one task; do not ask it to build the whole product in a single prompt.
3. Write/run the named failing behavioral check, implement minimum change, run package checks plus canonical kit checks.
4. Record evidence in your ledger; fix failures through systematic debugging. No paid calls for A/B. C/D paid work only at explicit live gates with designated operator.
5. Handoff commit, tests/exits, fixture/mode/provenance and remaining limitations. Empty suites or screenshots aren't package acceptance.

## Definition of done

All owned task acceptance checks exist and pass, relevant build/typechecks pass, schemas match, no hidden other-package dependency, no copied/renamed shared fields, no fake result labeled live, no secrets. Only live tasks with actual recorded calls are live-complete. Standalone module readiness is distinct from integrated application readiness.

## Handoff command

`python tools/acceptance_gate.py --package C` intentionally refuses missing app/tests. A green command gate still requires all named acceptance cases and human review.

Read [ENGINE_POLICY.md](../ENGINE_POLICY.md) before implementing search. It fixes proposal/strategy/refinement behavior without an extra paid planner call.
