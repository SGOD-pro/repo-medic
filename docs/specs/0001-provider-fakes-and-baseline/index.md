# 0001. Provider fakes and baseline stage

**Date**: 2026-10-10
**Status**: Accepted

## Summary

This specification defines deterministic provider fakes and the initial baseline verification stage for the repair engine. It ensures the engine validates incoming task recipes and proves the original project test suite passes twice before attempting any code modification. By keeping fake model and sandbox interfaces isolated, the engine tests all success and failure branches offline without network access or cloud charges.

## Requirements

**User stories**:
- As a repair engine runner, I want to validate task recipes before execution so that malformed requests fail early and cleanly.
- As an automated repair pipeline, I want to verify that the unpatched project passes its test suite twice so that unstable or already broken baselines are rejected before spending repair effort.
- As an engine developer, I want deterministic in memory fakes for model inference and sandbox execution so that full test suites run offline without network access.

**Acceptance criteria**:
- **AC-1**: The engine validates the task recipe to ensure required fields exist, the test command is nonempty, timeout seconds is positive, and allowed source paths are relative paths that do not escape the workspace root.
- **AC-2**: When recipe validation fails, the engine returns a failed RepairResult with an explanatory reason immediately without emitting a stage completed event.
- **AC-3**: The fake sandbox adapter provides deterministic execution results with configurable preset outcomes including clean pass, first check failure, second check failure, and test collection mismatch.
- **AC-4**: The fake model adapter provides a deterministic completion interface matching the model adapter protocol.
- **AC-5**: The baseline stage runs the preserved test command twice against the sandbox environment, requiring zero exit codes and identical test collection counts across both executions.
- **AC-6**: If the first baseline test execution fails, the engine emits a stage.completed event with stage baseline and passed false, then returns a failed RepairResult.
- **AC-7**: If the second baseline test execution fails or test collection counts diverge from the first execution, the engine emits a stage.completed event with stage baseline and passed false describing baseline instability, then returns a failed RepairResult.
- **AC-8**: When both baseline checks pass cleanly with stable collection, the engine emits a stage.completed event with stage baseline and passed true, allowing progression to subsequent stages.
- **AC-9**: The engine checks for cancellation via host ports before and between baseline checks, returning a cancelled RepairResult immediately if cancellation is signaled.
- **AC-10**: The baseline stage skips budget reservations in offline fake mode because simulated operations consume zero currency.

## Decision

**Chosen option**: Option 2: Dedicated adapter protocols with configurable fake presets

We separate model and sandbox adapter protocols and provide dedicated fake implementations with configurable presets for offline testing.

## Rationale

Reasoning and options: see rationale.md

## Feature design

**Data model sketch**:
- `CommandResult`: Holds exit_code (int), stdout (str), stderr (str), and collected_count (int).
- `SandboxPreset`: Enumeration of simulated behaviors: SUCCESS, FIRST_FAIL, SECOND_FAIL, UNSTABLE_COLLECTION, TIMEOUT.
- `SandboxAdapter`: Protocol with `async def execute_command(self, command: list[str], timeout_seconds: int) -> CommandResult`.
- `ModelAdapter`: Protocol with `async def complete(self, prompt: str, max_tokens: int) -> str`.
- `FakeSandboxAdapter`: In memory implementation of SandboxAdapter with configurable preset.
- `FakeModelAdapter`: In memory implementation of ModelAdapter returning canned patches.

**State transitions**:
1. START: Engine receives RepairRequest, TaskRecipe, and HostPorts.
2. VALIDATE_RECIPE: Recipe fields checked. If invalid, transition to TERMINAL_FAILED.
3. CANCEL_CHECK_1: Check host.cancelled(). If cancelled, transition to TERMINAL_CANCELLED.
4. BASELINE_CHECK_1: Execute test command in sandbox. If exit code non zero, emit stage.completed (passed=False) and transition to TERMINAL_FAILED.
5. CANCEL_CHECK_2: Check host.cancelled(). If cancelled, transition to TERMINAL_CANCELLED.
6. BASELINE_CHECK_2: Execute test command in sandbox second time. If exit code non zero or collection count differs, emit stage.completed (passed=False) and transition to TERMINAL_FAILED.
7. BASELINE_SUCCESS: Emit stage.completed (passed=True, stage="baseline"). Proceed to next repair slice.

**API surface**:
| Function or method | Scope | Key inputs | Key outputs | Auth | Key errors |
|---|---|---|---|---|---|
| `validate_recipe(recipe: TaskRecipe)` | Internal engine | recipe: TaskRecipe | None | None | ValueError on invalid fields |
| `FakeSandboxAdapter.execute_command(command, timeout_seconds)` | Internal engine | command: list[str], timeout_seconds: int | CommandResult | None | TimeoutError on simulated timeout |
| `FakeModelAdapter.complete(prompt, max_tokens)` | Internal engine | prompt: str, max_tokens: int | str | None | None |
| `run_baseline(recipe, sandbox, host)` | Internal engine | recipe: TaskRecipe, sandbox: SandboxAdapter, host: HostPorts | bool | None | None |
| `repair(request, recipe, host)` | Package entry point | request: RepairRequest, recipe: TaskRecipe, host: HostPorts | RepairResult | None | None |

**Value sourcing**:
| Action | Value produced / displayed | Source |
|---|---|---|
| Validate recipe | Error description string | Derived from validation check rule |
| Baseline check 1 | Exit code and collected test count | Produced by SandboxAdapter.execute_command |
| Baseline check 2 | Exit code and collected test count | Produced by SandboxAdapter.execute_command |
| Stability comparison | Equality boolean | Computed by comparing test collection counts |
| Emit stage event | stage name ("baseline") | Fixed stage literal defined in contracts |
| Emit stage event | passed flag | Computed from baseline check results |
| Emit stage event | summary string | Derived from execution outcome |
| Return RepairResult | state ("succeeded", "failed", "cancelled") | Derived from stage outcome and cancellation state |
| Return RepairResult | reason string | Descriptive outcome explanation |

**Key invariants**:
- The preserved test command is executed without alterations.
- Exactly two clean test passes are required before baseline is marked green.
- The engine emits documented events only and never emits run.finished.
- Engine code imports no HTTP routes, Web frameworks, or database modules.
- In offline fake mode with zero estimated cost, reservation calls to HostPorts are omitted.

**Security model**:
- All allowed source paths in TaskRecipe are verified to be relative paths without parent directory traversal (rejecting any components containing "..").
- The engine executes strictly inside isolated sandbox abstractions, using purely simulated in memory responses during offline runs.

**Configuration required**:
- No external environment variables or third party API tokens are required for offline provider fakes.

**Critical test scenarios**:
- Happy path: Valid recipe with clean double baseline pass emits stage.completed passed=True, verifies AC-5 and AC-8.
- Recipe validation failure: Path traversal attempt or empty test command fails immediately without events, verifies AC-1 and AC-2.
- First check failure: Baseline check 1 returns non zero exit code, emitting stage.completed passed=False and returning failed RepairResult, verifies AC-6.
- Second check failure: Baseline check 1 passes but check 2 fails, emitting instability summary and returning failed RepairResult, verifies AC-7.
- Collection divergence: Check 1 and check 2 report differing test counts, emitting instability summary and returning failed RepairResult, verifies AC-7.
- Cancellation before start: host.cancelled() returns True before execution, returning cancelled RepairResult, verifies AC-9.
- Cancellation between checks: host.cancelled() returns True after check 1, returning cancelled RepairResult, verifies AC-9.

## Build plan

- [x] 1. Define adapter protocol interfaces and CommandResult data structures in backend/src/engine/adapters.py, satisfies AC-3, AC-4
- [x] 2. Implement recipe validation utility rejecting empty commands and unsafe source paths in backend/src/engine/validation.py, satisfies AC-1, AC-2
- [x] 3. Implement FakeSandboxAdapter supporting configurable presets (success, fail first, fail second, unstable collection, timeout) in backend/src/engine/fake_sandbox.py, satisfies AC-3
- [x] 4. Implement FakeModelAdapter matching the ModelAdapter protocol in backend/src/engine/fake_model.py, satisfies AC-4
- [x] 5. Implement baseline stage runner performing double check execution, cancellation checks, and event emission in backend/src/engine/baseline.py, satisfies AC-5, AC-6, AC-7, AC-8, AC-9, AC-10
- [x] 6. Connect baseline runner into repair entry point in backend/src/engine/repair.py (or update fake_engine.py), satisfies AC-2, AC-6, AC-7, AC-8, AC-9
- [x] 7. Create comprehensive unit tests in backend/tests/engine/test_baseline.py covering all acceptance criteria, satisfies AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9, AC-10

## Consequences

**Positive**:
- Establishes a rigorous gate against broken or flaky baseline projects before any repair compute is spent.
- Enables exhaustive offline automated test coverage without network flakiness or paid provider dependencies.
- Clear adapter boundaries prepare the engine for seamless live provider integration in checkpoint K4.

**Negative / tradeoffs**:
- Running two full test checks during baseline doubles execution time compared to a single check.
- Fake adapters require ongoing maintenance to ensure their simulated outputs faithfully match real sandbox outputs.

**Neutral**:
- Engine tests remain isolated in backend/tests/engine/ and do not depend on D1 or FastAPI routers.

## Follow-up

- [ ] Implement slice 2 (sequential repair candidate generation) building on top of the established adapter protocols.
- [ ] Implement slice 3 (safe verifier and evidence collection) to verify patched candidates in fresh sandbox environments.
- [ ] Connect real Nebius Token Factory and ConTree sandbox adapters at checkpoint K4.
