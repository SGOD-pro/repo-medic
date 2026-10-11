# Verify: Safe verifier and evidence · spec 0003 · updated 2026-10-10

_Steps derived from spec 0003 acceptance criteria. `/check verify` runs these; `/test` locks the durable ones._

## Commands

- [x] `uv run pytest backend/tests/engine/test_verifier.py -k "test_baseline_preservation_records_hashes_and_node_ids"` → passes and captures baseline hashes and node IDs → AC-1
- [x] `uv run pytest backend/tests/engine/test_verifier.py -k "test_verifier_creates_fresh_execution_from_checkpoint"` → passes and verifies execution handle creation → AC-2
- [x] `uv run pytest backend/tests/engine/test_verifier.py -k "test_verifier_rejects_test_file_tampering"` → passes and fails candidate when test file hashes change → AC-3
- [x] `uv run pytest backend/tests/engine/test_verifier.py -k "test_verifier_handles_patch_apply_failure"` → passes and records patch apply failure → AC-4
- [x] `uv run pytest backend/tests/engine/test_verifier.py -k "test_verifier_rejects_node_id_mismatch"` → passes and fails candidate when collected node IDs diverge → AC-5
- [x] `uv run pytest backend/tests/engine/test_verifier.py -k "test_verifier_rejects_test_failures_or_new_skips"` → passes and rejects regressions or newly skipped tests → AC-6
- [x] `uv run pytest backend/tests/engine/test_verifier.py -k "test_verifier_rejects_dependency_version_mismatch"` → passes and rejects downgraded dependency version → AC-7
- [x] `uv run pytest backend/tests/engine/test_verifier.py -k "test_evidence_manifest_structure_and_offline_mode"` → passes and validates evidence.json fields → AC-8
- [x] `uv run pytest backend/tests/engine/test_verifier.py -k "test_artifact_persistence_failure_marks_candidate_failed"` → passes and returns artifact_persistence_failed without hiding test pass → AC-9
- [x] `uv run pytest backend/tests/engine/test_verifier.py -k "test_verifier_timeout_and_resource_cleanup"` → passes and confirms execution handle cleanup and timeout handling → AC-10

## Acceptance-criteria coverage

- AC-1: covered by baseline preservation capture step
- AC-2: covered by checkpoint execution provisioning step
- AC-3: covered by three point file hash tampering rejection step
- AC-4: covered by candidate patch apply step
- AC-5: covered by pytest collect node identifier set match step
- AC-6: covered by test exit code and zero new skips check step
- AC-7: covered by upgraded dependency version integrity step
- AC-8: covered by evidence manifest construction and mode labeling step
- AC-9: covered by artifact persistence and storage failure handling step
- AC-10: covered by execution timeout and resource cleanup step
