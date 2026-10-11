# Verify: sequential repair · spec 0002 · updated 2026-10-10
_Steps derived from spec 0002 acceptance criteria. /check verify runs these; /test locks the durable ones._

## UI / manual
- None (pure backend engine slice)

## Commands
- [x] `uv run pytest tests/engine/test_sequential_repair.py` → 24 unit tests pass covering baseline precondition, upgrade execution, failure reproduction, regex error extraction, prompt construction, patch safety, candidate verification, artifact persistence, and cancellation → AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9, AC-10, AC-11
- [x] `uv run python -m flake8 src tests` → zero lint warnings across all engine modules → AC-1
- [x] `uv run python -m mypy src tests` → typecheck passes cleanly with zero issues across 27 source files → AC-1
- [x] `uv run pytest` → full suite passes with 57 tests across baseline, sequential repair, and fakes → AC-1 through AC-11

## Acceptance criteria coverage
- AC-1 (baseline precondition): covered by test_sequential_repair_halts_on_baseline_failure in tests/engine/test_sequential_repair.py
- AC-2 (upgrade execution and failure reproduction): covered by test_derive_upgrade_command and test_upgrade_stage_success in tests/engine/test_sequential_repair.py
- AC-3 (upgrade failure gates): covered by test_upgrade_stage_install_failure, test_upgrade_stage_failure_not_reproduced, and test_upgrade_stage_unexpected_failure in tests/engine/test_sequential_repair.py
- AC-4 (regex error extraction with fallback): covered by test_extract_error_context_traceback, test_extract_error_context_pytest_summary, and test_extract_error_context_fallback in tests/engine/test_sequential_repair.py
- AC-5 (prompt construction and token bounds): covered by test_build_repair_prompt and test_candidate_generation_clean in tests/engine/test_sequential_repair.py
- AC-6 (budget reservation check): covered by test_candidate_generation_budget_reservation and test_candidate_generation_clean in tests/engine/test_sequential_repair.py
- AC-7 (unified diff parsing and safety validation): covered by test_parse_modified_files, test_validate_patch_allowed, test_validate_patch_disallowed_path, test_validate_patch_path_traversal, test_validate_patch_test_modification, and test_validate_patch_empty_diff in tests/engine/test_sequential_repair.py
- AC-8 (sandboxed candidate verification): covered by test_verify_candidate_patch_success, test_verify_candidate_patch_fails_tests, test_verify_candidate_patch_collection_mismatch, and test_verify_candidate_patch_new_skips in tests/engine/test_sequential_repair.py
- AC-9 (artifact persistence via HostPorts): covered by test_verify_candidate_patch_success and test_full_sequential_repair_pipeline_success in tests/engine/test_sequential_repair.py
- AC-10 (cooperative cancellation): covered by test_cancellation_during_sequential_repair in tests/engine/test_sequential_repair.py
- AC-11 (deterministic offline execution): covered by test_full_sequential_repair_pipeline_success in tests/engine/test_sequential_repair.py
