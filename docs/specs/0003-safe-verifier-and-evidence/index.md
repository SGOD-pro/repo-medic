# 0003. Safe verifier and evidence

**Date**: 2026-10-10
**Status**: Accepted

## Summary

This specification defines safe candidate verification and evidence generation for Repo Medic. Each candidate patch executes in a fresh sandbox created from an immutable upgraded checkpoint, preventing runtime contamination from previous runs. Verification confirms that all tests pass, collected test identifiers match baseline exactly, test files remain completely untampered, and the target dependency version remains intact. A structured evidence record along with patch diff and execution logs persist through host ports for both passing and failing candidates.

## Requirements

**User stories**:
- As an automated engine, I want verification to execute in a clean environment derived from an upgraded checkpoint so that candidate evaluation is isolated from build artifacts or contaminated process state.
- As a repository owner, I want strict verification that test files, runner configuration, and collected test identifiers are identical to baseline so that generated patches cannot disable, delete, or skip tests to fake a repair.
- As an evaluation consumer, I want a complete structured evidence manifest containing hashes, test metrics, and execution mode so that candidate fixes can be audited and replayed offline.
- As a pipeline operator, I want failed artifact storage to block declaring a candidate verified so that successful outcomes always have complete durable proof.

**Acceptance criteria**:
- **AC-1**: Baseline check records test collection node identifiers, total test counts, and sha256 hashes of all test files, `conftest.py`, and runner configuration files before repair work proceeds.
- **AC-2**: The verifier provisions a fresh isolated execution handle from the immutable upgraded checkpoint via `create_execution(checkpoint_id)` for each candidate evaluation, never reusing contaminated generation runtimes or relying on git reset.
- **AC-3**: The verifier validates preserved test and configuration file hashes against baseline records at three distinct checkpoints (pre patch application, post patch application, and post test execution), rejecting any candidate that modifies or tampers with test files.
- **AC-4**: The verifier applies only the validated candidate source patch inside the fresh isolated execution handle, recording an apply failure summary if patch application fails.
- **AC-5**: The verifier executes pytest collection with `--collect-only -q` in the patched execution environment, requiring nonzero collection and an exact set match of collected test node identifiers against baseline node identifiers.
- **AC-6**: The verifier executes the full preserved test command, requiring exit code zero, zero newly skipped tests, and zero newly xfailed tests.
- **AC-7**: The verifier verifies that the target dependency installed version matches `recipe.to_version` intact in the environment after test execution.
- **AC-8**: The verifier constructs a typed `EvidenceManifest` capturing candidate identity, task details, dependency versions, checkpoint identifier, test outcomes, verification checks, artifact hashes, and execution mode labeled explicitly as offline or live.
- **AC-9**: The verifier persists `evidence.json`, `patch.diff`, and `verify.log` artifacts through host `save_artifact` calls for both passing and failing candidate evaluations. If artifact storage fails, verification terminates with an explicit `artifact_persistence_failed` failure reason while preserving actual test outcomes.
- **AC-10**: The verifier enforces sandbox execution timeouts, cleans up sandbox execution resources upon completion or failure, and checks cancellation before verification operations.

## Decision

**Chosen option**: Option 1: Immutable checkpoint execution with three point hash invariants and typed evidence manifest

We enhance verification by creating an independent execution handle from the immutable upgraded checkpoint for every candidate. The verifier enforces identical test node identifiers and three point hash checks (pre patch, post patch, post test) across all test and configuration files. It constructs a typed `EvidenceManifest` record, persists `evidence.json`, `patch.diff`, and `verify.log`, and prevents declaring success if required artifact storage fails.

## Feature design

**Data model sketch**:
- `TestPreservationRecord`: root_dir (str), file_hashes (dict of file path to sha256 hex string), node_ids (list of str), collected_count (int).
- `VerificationChecks`: checkpoint_isolated (bool), pre_patch_hash_match (bool), patch_applied (bool), post_patch_hash_match (bool), collection_node_ids_match (bool), tests_passed (bool), zero_new_skips (bool), post_test_hash_match (bool), version_intact (bool), artifacts_persisted (bool).
- `EvidenceManifest`: schema_version (str, "1.0.0"), candidate_id (str), task_id (str), commit_hash (str), dependency (str), from_version (str), to_version (str), verified_version (str), checkpoint_id (str), execution_mode (str, "offline" or "live"), checks (VerificationChecks), test_summary (dict with exit_code, collected_count, passed_count, failed_count, skipped_count, xfailed_count), artifact_hashes (dict of artifact name to sha256 hex string), duration_seconds (float), created_at (str).
- `CandidateVerification`: candidate_id (str), passed (bool), reason (str), exit_code (int), stdout (str), stderr (str), collected_count (int), skipped_count (int), xfailed_count (int), installed_version (str), manifest (EvidenceManifest or None), summary (str), duration_seconds (float).

**State transitions**:
1. START: Receive candidate patch, task recipe, host ports, and baseline preservation record.
2. CHECK_CANCEL: Check `host.cancelled()`. If cancelled, return cancelled outcome.
3. PROVISION_EXECUTION: Call `sandbox.create_execution(checkpoint_id)` to acquire fresh execution handle.
4. VERIFY_PRE_PATCH_HASHES: Verify test and config file hashes match baseline. If mismatch, fail with `test_tampering_detected`.
5. APPLY_PATCH: Apply validated patch. If nonzero exit code or timeout, save logs and fail with `patch_apply_failed`.
6. VERIFY_POST_PATCH_HASHES: Verify test and config file hashes remain identical to baseline. If mismatch, fail with `test_tampering_detected`.
7. COLLECT_TESTS: Run pytest with `--collect-only -q`. Compare node identifiers against baseline list. If mismatch or empty, save logs and fail with `test_ids_mismatch`.
8. RUN_TESTS: Execute recipe test command. If nonzero exit code or timeout or new skips, record failure.
9. VERIFY_POST_TEST_HASHES: Verify test and config file hashes remain untampered after test execution. If mismatch, fail with `test_tampering_detected`.
10. VERIFY_VERSION: Verify installed dependency matches `recipe.to_version`. If mismatch, fail with `dependency_version_mismatch`.
11. COMPILE_EVIDENCE: Construct typed `EvidenceManifest`, compute artifact sha256 hashes, serialize `evidence.json`.
12. PERSIST_ARTIFACTS: Call `host.save_artifact` for `evidence.json`, `patch.diff`, and `verify.log`. If storage raises an error, set outcome to failed with `artifact_persistence_failed`.
13. CLEANUP: Call execution handle cleanup, release resources.
14. EMIT_COMPLETION: Emit `candidate.completed` and `stage.completed` (stage="verification") events. Return `CandidateVerification`.

**API surface**:
| Function or method | Scope | Key inputs | Key outputs | Auth | Key errors |
|---|---|---|---|---|---|
| `record_baseline_preservation(recipe, sandbox)` | Internal engine | recipe: TaskRecipe, sandbox: SandboxAdapter | TestPreservationRecord | None | TimeoutError, RuntimeError |
| `verify_candidate_patch(candidate, recipe, sandbox, host, baseline_preservation, checkpoint_id)` | Internal engine | candidate: CandidatePatch, recipe: TaskRecipe, sandbox: SandboxAdapter, host: HostPorts, baseline_preservation: TestPreservationRecord, checkpoint_id: str | CandidateVerification | None | TimeoutError |
| `build_evidence_manifest(candidate, recipe, checks, test_res, artifact_hashes, mode, duration)` | Internal engine | CandidatePatch, TaskRecipe, VerificationChecks, CommandResult, dict, str, float | EvidenceManifest | None | ValueError |
| `SandboxAdapter.create_execution(checkpoint_id)` | Internal engine protocol | checkpoint_id: str | SandboxAdapter | None | KeyError, RuntimeError |

**Value sourcing**:
| Action | Value produced / displayed | Source |
|---|---|---|
| Record baseline preservation | Baseline test hashes and node IDs | Sandbox command execution of pytest collect and sha256 hashing of test files |
| Create isolated execution | Clean execution sandbox | `sandbox.create_execution(checkpoint_id)` derived from upgrade checkpoint |
| Verify file integrity | Hash match boolean | Cryptographic comparison of current file hashes against baseline hashes |
| Verify test collection | Node identifier match boolean | Set comparison of collected test node strings against baseline node strings |
| Verify dependency version | Version match boolean | Sandbox package inspection compared to `recipe.to_version` |
| Build evidence manifest | Serialized `evidence.json` | Aggregated verification metrics, computed artifact hashes, and recipe metadata |
| Persist artifacts | Storage confirmation | Return values of `host.save_artifact` for evidence, patch, and log kinds |
| Verification outcome | `CandidateVerification` state and reason | Composite evaluation of execution results, invariants, and storage success |

**Key invariants**:
- Verification never mutates or executes inside the candidate generation sandbox instance.
- Candidate patch is rejected if any test file, `conftest.py`, or test runner configuration is modified.
- Verification requires collected test node identifiers to match baseline node identifiers identically.
- Verification requires zero exit code and zero newly skipped or xfailed tests.
- Every evaluation attempts saving `evidence.json`, `patch.diff`, and `verify.log`.
- Failure to persist required artifacts marks candidate verification as failed with reason `artifact_persistence_failed`.
- Execution mode in `evidence.json` is explicitly labeled "offline" or "live", preserved during replay.
- Engine code never emits `run.finished` and never invents unsupported events.

**Security model**:
- Source patches modifying files outside allowed source paths were already rejected by patch validator.
- Three point hash verification guarantees zero modification to test infrastructure or execution scripts.
- Execution handle cleanup ensures sandboxed temporary directories and processes are purged.
- Evidence manifest excludes sensitive environment credentials or secret variables.

**Configuration required**:
- `REPOMEDIC_MODE`: defaults to "offline", sets execution mode in evidence manifest.
- `REPOMEDIC_MAX_LOG_BYTES`: defaults to 1048576 (1 MB) to bound verify.log size.

**Critical test scenarios**:
- Clean verification: Candidate passes all tests, node IDs match baseline, file hashes match baseline, artifacts save cleanly, verifies **AC-1**, **AC-2**, **AC-5**, **AC-6**, **AC-7**, **AC-8**, **AC-9**.
- Test file tampering: Candidate attempts editing `tests/test_app.py` or `conftest.py`, caught by hash check and rejected, verifies **AC-3**.
- Test collection suppression: Candidate drops a test or changes collection, caught by node ID comparison and rejected, verifies **AC-5**.
- Test execution regression: Candidate tests fail or introduce new skips, recorded as failure and artifacts saved, verifies **AC-6**, **AC-9**.
- Upgraded version mismatch: Target dependency package version is downgraded or changed, caught and rejected, verifies **AC-7**.
- Artifact persistence failure: Test execution passes but host save artifact raises an error, marked as failed with `artifact_persistence_failed`, verifies **AC-9**.
- Timeout and cleanup: Test command times out, resources cleaned up, partial logs saved, verifies **AC-10**.

## Build plan

- [x] 1. Define `TestPreservationRecord`, `VerificationChecks`, and `EvidenceManifest` dataclasses in `backend/src/engine/candidate.py`, satisfies **AC-1**, **AC-8**
- [x] 2. Implement baseline preservation recorder in `backend/src/engine/baseline.py` to capture test node IDs and test file hashes, satisfies **AC-1**
- [x] 3. Update `SandboxAdapter` protocol in `backend/src/engine/adapters.py` and `FakeSandboxAdapter` in `backend/src/engine/fake_sandbox.py` with `create_execution(checkpoint_id)` and execution cleanup, satisfies **AC-2**, **AC-10**
- [x] 4. Implement three point hash validator and pytest collect comparison helpers in `backend/src/engine/verifier.py`, satisfies **AC-3**, **AC-5**
- [x] 5. Implement evidence manifest builder and serializer in `backend/src/engine/verifier.py`, satisfies **AC-8**
- [x] 6. Refactor `verify_candidate_patch` in `backend/src/engine/verifier.py` to run in isolated execution, enforce test invariants, persist `evidence.json`, and handle artifact storage failures, satisfies **AC-2**, **AC-4**, **AC-6**, **AC-7**, **AC-9**, **AC-10**
- [x] 7. Wire checkpoint identifier and baseline preservation into `backend/src/engine/repair.py`, satisfies **AC-1**, **AC-2**
- [x] 8. Add comprehensive unit tests in `backend/tests/engine/test_verifier.py` covering all invariant checks, tampering rejections, artifact storage failures, and presets, satisfies **AC-1**, **AC-2**, **AC-3**, **AC-4**, **AC-5**, **AC-6**, **AC-7**, **AC-8**, **AC-9**, **AC-10**

## Consequences

**Positive**:
- Guarantees complete isolation during verification by creating fresh execution handles from the upgraded checkpoint.
- Prevents sneaky models from faking repairs by deleting, modifying, or skipping tests.
- Delivers a structured, auditable `evidence.json` artifact for evaluation and replay.
- Makes artifact storage a required gate, preventing silent evidence loss.

**Negative / tradeoffs**:
- Executing pytest collect only adds an extra command invocation before test execution.
- Hashing test files requires computing sha256 hashes of test tree files during baseline and verification.

**Neutral**:
- Interfaces remain fully compatible with offline fake adapters now, ready for live provider adapter mapping in checkpoint K4.

## Follow-up

- [ ] Checkpoint K4: Map `create_execution` to live Nebius provider sandbox snapshot or container provisioning.
- [ ] Slice D coordination: Ensure `evidence.json` schema matches downstream evaluation checker expectations.

## Rationale

Reasoning, alternatives considered, and tradeoffs: see rationale.md
