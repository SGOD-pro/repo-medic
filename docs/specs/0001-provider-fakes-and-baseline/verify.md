# Verify: provider fakes and baseline · spec 0001 · updated 2026-10-10
_Steps derived from spec 0001 acceptance criteria. /check verify runs these; /test locks the durable ones._

## UI / manual
- None (pure backend engine slice)

## Commands
- [x] `uv run pytest tests/engine/test_baseline.py` → 17 unit tests pass covering recipe validation, presets, double check, flakiness, cancellation, and invariants → AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9, AC-10
- [x] `uv run python -m flake8 src tests` → zero lint warnings or style errors across all engine modules → AC-1
- [x] `uv run python -m mypy src tests` → typecheck passes with zero issues across 18 source files → AC-1
- [x] `uv run pytest` → full suite passes with 23 tests across baseline, fakes, and smoke tests → AC-5, AC-8

## Acceptance criteria coverage
- AC-1 (recipe validation rules): covered by test_recipe_validation_* in tests/engine/test_baseline.py
- AC-2 (fail immediately without events): covered by test_repair_fails_immediately_on_invalid_recipe in tests/engine/test_baseline.py
- AC-3 (configurable sandbox presets): covered by test_fake_sandbox_presets in tests/engine/test_baseline.py
- AC-4 (fake model adapter protocol): covered by test_fake_model_adapter in tests/engine/test_baseline.py
- AC-5 (double baseline execution): covered by test_baseline_success in tests/engine/test_baseline.py
- AC-6 (first check failure handling): covered by test_baseline_first_check_failure in tests/engine/test_baseline.py
- AC-7 (second check instability and collection divergence): covered by test_baseline_second_check_failure_instability and test_baseline_unstable_collection_failure in tests/engine/test_baseline.py
- AC-8 (clean baseline pass event emission): covered by test_baseline_success in tests/engine/test_baseline.py
- AC-9 (cancellation before and between checks): covered by test_cancellation_before_execution and test_cancellation_between_checks in tests/engine/test_baseline.py
- AC-10 (zero budget reservation in fake mode): covered by test_baseline_success in tests/engine/test_baseline.py
