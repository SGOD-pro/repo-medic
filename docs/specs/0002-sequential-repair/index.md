# 0002. Sequential repair loop

**Date**: 2026-10-10
**Status**: Accepted

## Summary

This specification defines the sequential repair loop for Repo Medic (Slice C Feature 2). Following a clean baseline double check, the engine upgrades the targeted dependency in an isolated sandbox, confirms the expected upgrade failure, extracts a bounded error block, prompts the model for a candidate patch, validates patch safety against allowed source paths, and verifies the candidate in a clean environment. All stages run deterministically offline using fake provider adapters before connecting live Nebius providers in checkpoint K4.

## Requirements

**User stories**:
- As a repair pipeline, I want to verify that upgrading the target dependency reproduces the expected failure so that repair work only proceeds on genuine regressions.
- As an automated engine, I want to extract concise error blocks using regex so that the model receives relevant context without exceeding token budgets.
- As a repository owner, I want strict patch validation so that generated patches cannot escape workspace directories or touch test files, configuration, or lockfiles.
- As a repair evaluator, I want verification to run against fresh environments and compare collection counts, skip counts, and dependency versions so that partial or fake fixes are rejected.

**Acceptance criteria**:
- **AC-1**: Sequential repair requires a successful baseline double check before starting. If baseline fails or signals cancellation, sequential repair stops immediately.
- **AC-2**: The engine derives the upgrade command from recipe.dependency and recipe.to_version (executing pip install {recipe.dependency}=={recipe.to_version}) in the sandbox, verifying the installed version and reproducing the expected failure from recipe.expected_failure with nonzero exit code and matching failure output indicators.
- **AC-3**: If the upgrade fails to install, or if running the test command after upgrade returns exit code zero or fails to reproduce recipe.expected_failure, the engine emits a stage completed event with stage upgrade and passed false, returning a failed repair result.
- **AC-4**: The engine extracts the error block and failing file names from upgrade test logs using regex matching, falling back to a bounded tail of the execution log when regex extraction finds no blocks.
- **AC-5**: The engine constructs a model prompt containing task instructions, upgrade details, extracted error context, and current contents of allowed source files, capping model completion tokens to 2048.
- **AC-6**: Before invoking model completion, the engine calls host reserve for estimated operation cost, skipping reservation when running in offline fake mode with zero cost.
- **AC-7**: The engine parses the model completion as a unified diff, derives modified file paths from diff headers, and rejects any patch touching files outside allowed source paths, containing path traversal, escaping symlinks, or editing tests, configuration, or lockfiles.
- **AC-8**: The engine verifies the candidate patch in a fresh clean sandbox by executing the preserved test command, requiring exit code zero, test collection count matching baseline, zero newly skipped or xfailed tests, and target upgraded dependency version intact.
- **AC-9**: The engine persists patch diff as patch.diff and execution logs as verify.log through host save artifact for both passing and failing candidate evaluations.
- **AC-10**: The engine checks cancellation via host cancelled before upgrade, before model prompting, and before candidate verification, saving available artifacts and returning a cancelled repair result when signaled.
- **AC-11**: The sequential repair pipeline runs entirely offline using fake sandbox and model adapters with configurable presets, requiring zero external network calls or paid provider credentials for acceptance testing.

## Decision

**Chosen option**: Option 1: Modular stage pipeline with strict diff validation and fresh sandbox verification

We structure sequential repair into distinct testable stage helpers: dependency upgrade, bounded prompt construction with regex extraction, candidate patch validation, fresh sandbox verification, and artifact persistence. All stages interact through SandboxAdapter and ModelAdapter protocols, tested offline with deterministic presets.

## Rationale

Reasoning, alternatives considered, and tradeoffs: see rationale.md

## Feature design

**Data model sketch**:
- `UpgradeResult`: success (bool, requiring installation and expected failure reproduction), installed_version (str), failure_output (str), exit_code (int).
- `CandidatePatch`: candidate_id (str), diff_content (str), modified_files (list of str, derived from diff headers), raw_model_response (str).
- `PatchValidationResult`: valid (bool), reason (str), violations (list of str).
- `CandidateVerification`: candidate_id (str), passed (bool), exit_code (int), stdout (str), stderr (str), collected_count (int), skipped_count (int), xfailed_count (int), installed_version (str), duration_seconds (float).
- `SequentialRepairOutcome`: state (str, restricted to succeeded, failed, cancelled), reason (optional str), candidate (optional CandidatePatch), verification (optional CandidateVerification), upgrade (optional UpgradeResult).

**State transitions**:
1. START: Receive RepairRequest, TaskRecipe, and HostPorts.
2. BASELINE: Execute run baseline stage. If not passed, transition to TERMINAL.
3. CANCEL_CHECK_1: Check host cancelled. If cancelled, transition to TERMINAL_CANCELLED.
4. UPGRADE: Derive upgrade command from recipe.dependency and recipe.to_version. Execute upgrade command in sandbox. Verify installed package version and test failure matching recipe.expected_failure. If failed, emit stage completed event with stage upgrade and passed false, then transition to TERMINAL_FAILED.
5. CANCEL_CHECK_2: Check host cancelled. If cancelled, transition to TERMINAL_CANCELLED.
6. GENERATE_CANDIDATE: Extract error block via regex, construct prompt, reserve budget if cost positive, call model complete, parse unified diff.
7. VALIDATE_PATCH: Verify diff paths match allowed source paths without traversal. If invalid, transition to TERMINAL_FAILED.
8. CANCEL_CHECK_3: Check host cancelled. If cancelled, transition to TERMINAL_CANCELLED.
9. VERIFY_CANDIDATE: Apply patch to clean sandbox, execute test command, verify exit code zero, matching collection count, zero new skips, intact version. Emit candidate.completed event and stage completed event with stage verification and passed outcome. Save patch.diff and verify.log via host.
10. SUCCESS: Return succeeded RepairResult.

**API surface**:
| Function or method | Scope | Key inputs | Key outputs | Auth | Key errors |
|---|---|---|---|---|---|
| `run_upgrade_stage(recipe, sandbox, host)` | Internal engine | recipe: TaskRecipe, sandbox: SandboxAdapter, host: HostPorts | UpgradeResult | None | TimeoutError on command timeout |
| `extract_error_context(log_text)` | Internal engine | log_text: str | tuple of error block str and file list | None | None |
| `generate_candidate(recipe, upgrade, model, host)` | Internal engine | recipe: TaskRecipe, upgrade: UpgradeResult, model: ModelAdapter, host: HostPorts | CandidatePatch | None | BudgetExceededError on reservation denial |
| `validate_patch(diff_text, recipe)` | Internal engine | diff_text: str, recipe: TaskRecipe | PatchValidationResult | None | None |
| `verify_candidate(candidate, recipe, sandbox, host, baseline)` | Internal engine | candidate: CandidatePatch, recipe: TaskRecipe, sandbox: SandboxAdapter, host: HostPorts, baseline: BaselineOutcome | CandidateVerification | None | TimeoutError on verification timeout |
| `repair(request, recipe, host, sandbox, model)` | Package entry point | request: RepairRequest, recipe: TaskRecipe, host: HostPorts, sandbox: Optional, model: Optional | RepairResult | None | None |

**Value sourcing**:
| Action | Value produced / displayed | Source |
|---|---|---|
| Upgrade dependency | Upgrade command and package version | Command synthesized as pip install {recipe.dependency}=={recipe.to_version} from recipe.dependency and recipe.to_version |
| Verify upgrade failure | Failure match boolean | Substring or regex comparison of test output against recipe.expected_failure |
| Extract error block | Error block snippet | Regex match on python traceback or test summary lines |
| Build model prompt | Complete prompt string | Combined recipe prompt, allowed source files, and error block |
| Reserve budget | Reservation confirmation | HostPorts reserve call with estimated cost |
| Model completion | Raw diff patch string | ModelAdapter complete call |
| Parse modified files | Modified file path list | Regex extraction of diff header paths (+++ and ---) |
| Validate patch paths | Path safety boolean | Comparison of modified files against recipe allowed source paths |
| Candidate verification | Test exit code and counts | CommandResult from sandbox test execution |
| Save artifacts | Persisted artifact identifiers | HostPorts save artifact calls for patch.diff and verify.log |
| Emit stage events | Event payload | Generated stage outcome dictionaries |
| Final outcome | RepairResult state and reason | Derived from sequential repair pipeline outcome |

**Key invariants**:
- Exactly one candidate patch is generated and evaluated in this sequential slice.
- Patches modifying files outside recipe allowed source paths are rejected before sandbox execution.
- Verification requires collected count greater than zero, matching baseline count, and zero new skips.
- Every candidate evaluation saves patch.diff and verify.log artifacts through host ports.
- Engine code never imports HTTP routers or database repositories and never emits run finished.
- In offline fake mode with zero cost, host reserve calls are omitted.

**Security model**:
- Patches touching paths with parent directory traversal, absolute paths, or symlink escapes are rejected.
- Patches touching test directories, configuration files, or dependency manifests are rejected.
- All artifact paths are sanitized to prevent directory traversal in host storage.

**Configuration required**:
- `REPOMEDIC_MODE`: offline default; live mode activated when operator provides credentials in K4.
- `REPOMEDIC_MAX_OUTPUT_TOKENS`: defaults to 2048.
- No live credentials required for offline tests.

**Critical test scenarios**:
- Happy path: Clean baseline, successful upgrade failure reproduction, valid candidate patch generation, clean candidate verification, verifies AC-1, AC-2, AC-5, AC-7, AC-8, AC-9.
- Upgrade failure mismatch: Upgrade test passes or produces unexpected failure output, stopping pipeline, verifies AC-3.
- Unsafe patch rejection: Model emits diff targeting files outside allowlist or escaping traversal, rejecting patch, verifies AC-7.
- Verification regression: Candidate patch fails tests, changes test collection count, or introduces new skips, failing candidate and saving artifacts, verifies AC-8, AC-9.
- Cancellation handling: Cancellation before upgrade, before inference, or before verification stops run and saves available evidence, verifies AC-10.
- Offline determinism: Complete pipeline runs without network access using FakeSandboxAdapter and FakeModelAdapter presets, verifies AC-11.

## Build plan

- [x] 1. Define internal data structures in backend/src/engine/candidate.py (UpgradeResult, CandidatePatch, PatchValidationResult, CandidateVerification), satisfies AC-2, AC-7, AC-8
- [x] 2. Implement error context extraction utility in backend/src/engine/extraction.py supporting regex traceback extraction with log fallback, satisfies AC-4
- [x] 3. Implement upgrade stage runner in backend/src/engine/upgrade.py deriving pip install command from recipe.dependency and recipe.to_version and verifying recipe.expected_failure reproduction, satisfies AC-2, AC-3
- [x] 4. Implement unified diff parser and patch safety validator in backend/src/engine/patch_validator.py checking allowed source paths and traversal safety, satisfies AC-7
- [x] 5. Implement candidate generation in backend/src/engine/candidate_generator.py with budget reservation and prompt construction, satisfies AC-5, AC-6
- [x] 6. Implement candidate verification runner in backend/src/engine/verifier.py enforcing clean sandbox execution, collection consistency, skip checks, and artifact saving, satisfies AC-8, AC-9
- [x] 7. Update backend/src/engine/fake_sandbox.py and backend/src/engine/fake_model.py with sequential repair presets (upgrade failure, unsafe patch, verification failure, clean fix), satisfies AC-11
- [x] 8. Wire sequential repair loop into backend/src/engine/repair.py coordinating baseline, upgrade, generation, validation, verification, and cancellation, satisfies AC-1, AC-10
- [x] 9. Add unit tests in backend/tests/engine/test_sequential_repair.py covering all acceptance criteria, satisfies AC-1 through AC-11

## Consequences

**Positive**:
- Provides a deterministic end to end automated repair pipeline from upgrade reproduction to candidate verification.
- Enforces strict security boundaries stopping prompt injection or unsafe patches from editing unauthorized files.
- Operates entirely offline with configurable presets, allowing rapid reliable test execution without API costs.

**Negative / tradeoffs**:
- Single sequential candidate attempt cannot recover if the first candidate fails tests (addressed in later branch and refine slice).
- Regex error extraction may occasionally fall back to log tails for non standard test frameworks.

**Neutral**:
- Follows established adapters protocol, preparing seamlessly for real Nebius provider integration at checkpoint K4.

## Follow-up

- [ ] Slice 3: Implement safe verifier and evidence collection with secondary validation environments.
- [ ] Slice 4: Implement bounded branch and refine search (up to 3 candidates with 1 refinement each).
- [ ] Checkpoint K4: Connect live Nebius Token Factory model and sandbox adapters using operator API keys.
