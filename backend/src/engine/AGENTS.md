# Engine (Package C)

Core repair engine for Repo Medic. This package validates task recipes, runs baseline checks, coordinates repair attempts, and communicates through host ports.

## Local files

- `adapters.py`: Sandbox and model adapter protocols, command result types, and preset enumerations.
- `fake_sandbox.py`: In memory fake sandbox adapter with configurable presets for testing.
- `fake_model.py`: In memory fake model adapter returning canned patches.
- `validation.py`: Recipe validation checking commands, timeouts, and safe source paths.
- `baseline.py`: Baseline stage runner executing the test command twice and comparing stability.
- `upgrade.py`: Dependency upgrade execution and expected failure reproduction runner.
- `extraction.py`: Error context and failure traceback bounded extraction.
- `candidate.py`: Data models for candidate patches, attempts, budgets, and verification results.
- `candidate_generator.py`: Prompt construction and candidate/refinement patch generation.
- `patch_validator.py`: Patch safety, allowed source paths, and traversal escape validation.
- `verifier.py`: Isolated candidate verification, file hash checks, collection matching, and evidence manifest persistence.
- `branch_search.py`: Bounded depth first branch and refine search coordinator with early stopping.
- `token_factory_model.py`: Live model adapter connecting to Nebius Token Factory with zero SDK retries.
- `contree_sandbox.py`: Live sandbox adapter wrapping ConTree SDK with checkpoint branching and cleanup.
- `repair.py`: Package entry point coordinating baseline, upgrade, and repair search routing.

## Commands

- Run engine unit tests: `uv run pytest tests/engine/`
- Run all backend tests: `uv run pytest`
- Check linting: `uv run python -m flake8 src tests`
- Check type signatures: `uv run python -m mypy src tests`

## Conventions and constraints

- Respect team ownership boundaries. Package C owns engine logic, baseline, and adapters. Package B owns public routes and the final run finished event. The engine never emits run finished.
- Keep engine code independent of HTTP routes, database access, and web frameworks.
- Emit only documented events such as stage completed and candidate completed.
- Validate task recipes strictly. Disallow path traversal and empty test commands.
- Run baseline checks twice. Both executions must return exit code zero with identical test collection counts.
- Check cancellation via host ports before and between operations.
- Bound tree search to at most 3 candidate branches and at most 1 refinement per branch.
- Provision fresh sandbox handles from immutable checkpoints for every candidate evaluation.
- Governing specs: [0001-provider-fakes-and-baseline](../../docs/specs/0001-provider-fakes-and-baseline/index.md), [0002-sequential-repair](../../docs/specs/0002-sequential-repair/index.md), [0003-safe-verifier-and-evidence](../../docs/specs/0003-safe-verifier-and-evidence/index.md), [0004-bounded-branch-and-refine](../../docs/specs/0004-bounded-branch-and-refine/index.md), [0006-live-provider-integration](../../docs/specs/0006-live-provider-integration/index.md)

_Drafted by /sync from the introducing change, worth a quick human pass._
