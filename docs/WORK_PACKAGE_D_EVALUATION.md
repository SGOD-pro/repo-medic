# D — evaluation and demo evidence handoff

Read [shared rules](../AGENTS.md), [product](PRD.md), [architecture](ARCHITECTURE.md) and [build plan](phases.md). Optional fourth teammate owns this; with three, the foundation owner handles the minimum version. Start offline work at `foundation-ready`, not after the entire app finishes.

## Own and build

Own `backend/src/evaluation/` and `backend/tests/evaluation/`. Propose shared fixture additions to the foundation owner. Do not create new model/sandbox adapters or change the product API.

First build an offline runner using C's repair interface and fakes. Validate result/evidence consistency, budget denial, failure preservation and replay labeling. Store each experiment in a local timestamped output folder with task, method, seed/config, attempts, logs, result, time and usage. Keep it simple: JSON plus a small human-readable table, no new database or dashboard service.

Real evaluation starts after integrated offline checks and the initial live repair pass. A single operator runs explicit live experiments within the remaining allowance. Controls: one-shot repair, independent candidates, sequential refinement and branch/refine. Compare multi-attempt methods using the same tasks, model, verifier and total cost/token/time caps; report actual consumption and unequal usage. Small samples are descriptive, not proof of general superiority.

Never erase failed runs or fabricate missing baseline numbers. A saved replay can support a demonstration but cannot count as a newly solved task. Preserve sanitized real failures as offline regressions.

## Demo script and user explanation

Check organizer duration/format rules first. Suggested approximately three-minute story:

- 0:00–0:20: show a maintainer's dependency-upgrade failure and state the use case.
- 0:20–0:45: enter the app, choose the curated task and show exact upgrade plus live/replay label.
- 0:45–1:45: show real stages: green baseline, red upgraded tests, bounded repair, fresh verification. Label edited time jumps; do not disguise stored replay as live execution.
- 1:45–2:30: open patch/evidence, show preserved tests and tested versions, download artifacts and explain maintainer review/apply.
- 2:30–3:00: show actual spend, measured comparison if available, and limitations. Avoid unsupported win or performance claims.

## Acceptance checks

Runner defaults offline even when keys exist. Live requires an explicit flag and budget caps. It never automatically retries unknown submissions. Raw outcomes reconcile with summary counts; evidence validates hashes, versions and mode. Demo contains actual provider evidence for any live claim. Replay examples and mock fixtures are labeled. Regression checks pass before requesting another paid test.

Use `/test` for evaluation invariants, `/debug` mismatches, `/check verify` final app flow and `/document` final submission text. Keep the report within experiment outputs or the PR; another permanent specification bundle is unnecessary.
