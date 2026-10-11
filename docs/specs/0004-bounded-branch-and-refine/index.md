# 0004. Bounded branch and refine search

**Date**: 2026-10-11
**Status**: Accepted

## Summary

This specification defines bounded branch and refine repair search for Repo Medic. When repairs require exploring multiple candidate solutions, the engine systematically generates up to three candidate branches and allows up to one refinement attempt per candidate branch. Every verification step executes inside a fresh sandbox handle derived from the immutable upgraded checkpoint. Search terminates early upon the first passing candidate, respects cost reservations and cancellation, and persists evidence for every attempt without exceeding provider caps.

## Requirements

**User stories**:
- As a repair engine, I want to explore alternative fix branches when an initial candidate patch fails so that tough dependency upgrades can still be repaired automatically.
- As an automated system, I want to provide failing test feedback to refine a promising candidate once so that minor syntax or assertion mistakes can be corrected.
- As a repository owner, I want strict exploration limits capping search to at most three branches and one refinement per branch so that automated repairs never loop indefinitely or consume excessive tokens.
- As a platform operator, I want budget reservation and cancellation checks around all model generations so that unpaid or cancelled runs abort immediately and cleanly.
- As an evaluation auditor, I want every candidate and refinement attempt to execute in fresh isolated sandboxes and record complete evidence manifests so that each evaluation remains reproducible and uncontaminated.

**Acceptance criteria**:
- **AC-1**: When `request.search_mode` equals `branch_refine`, the engine dispatches to bounded branch and refine search after successful baseline and upgrade stages. If `request.search_mode` equals `sequential`, the engine continues using single candidate sequential repair.
- **AC-2**: The engine strictly enforces tree search limits, generating at most 3 root candidate branches (`recipe.max_candidates` capped at 3) and at most 1 refinement attempt per candidate branch (`recipe.max_refinements` capped at 1), capping total attempts at 6.
- **AC-3**: The engine schedules exploration in depth first order, evaluating candidate 1 first, immediately attempting refinement 1 if candidate 1 fails with actionable test feedback, and only advancing to candidate 2 if refinement 1 fails.
- **AC-4**: When a candidate fails verification due to test failure or apply failure, the engine constructs a refinement prompt containing task context, original error context, previous diff content, and failing verification logs, capping completion tokens at 2048. If a candidate patch is rejected by patch safety validation, refinement is skipped and search moves to the next branch.
- **AC-5**: The engine validates every candidate patch and refinement patch against allowed source paths and safety rules using `validate_patch` before any sandbox execution, rejecting patches that touch forbidden files.
- **AC-6**: Every verification evaluation (root candidate or refinement) executes inside a fresh independent execution handle provisioned via `sandbox.create_execution(checkpoint_id)` from the immutable upgraded checkpoint, never reusing prior runtimes.
- **AC-7**: Before each model generation or refinement call, the engine reserves cost via `host.reserve(operation_id, estimated_cost)`. If reservation returns false, search stops immediately returning `state="failed"` with reason `budget_exceeded`.
- **AC-8**: The engine checks cancellation via `host.cancelled()` before every generation call, before every verification step, and before every refinement attempt, releasing sandbox resources and returning `state="cancelled"` when signaled.
- **AC-9**: The engine stops exploration immediately upon the first candidate or refinement that passes all verifier checks, emitting `candidate.completed` and returning `state="succeeded"`.
- **AC-10**: The engine persists `patch.diff`, `verify.log`, and `evidence.json` via `host.save_artifact` for every evaluated attempt using attempt specific names like `{attempt_id}_evidence.json` to prevent overwriting prior evidence, and saves canonical `evidence.json` for the winning attempt.
- **AC-11**: If all permitted branches and refinements fail verification, the engine terminates cleanly and returns `state="failed"` with an explanatory summary of attempts, without emitting `run.finished`.
- **AC-12**: All branch and refine search logic executes offline deterministically using fake model and fake sandbox adapters, requiring zero network calls or paid API keys during acceptance testing.

## Decision

**Chosen option**: Option 1: Depth first search with immediate single refinement, budget reservations, and fresh checkpoint execution

We coordinate branch and refine search using a dedicated scheduler module that explores up to three candidate branches in depth first order with at most one refinement per branch. Before every model completion, the scheduler reserves budget via host ports. Before every verification, it provisions a fresh isolated execution handle from the upgraded checkpoint. The search terminates on the first verified candidate, records evidence manifests for every attempt, and stops cleanly on cancellation or budget exhaustion.

## Feature design

**Data model sketch**:
- `BranchAttempt`:
  - `attempt_id`: string (for example `candidate_1` or `candidate_1_refine_1`)
  - `branch_index`: integer (1 to 3)
  - `is_refinement`: boolean
  - `parent_candidate_id`: optional string
  - `patch`: `CandidatePatch`
  - `validation`: `PatchValidationResult`
  - `verification`: optional `CandidateVerification`
  - `duration_seconds`: float
- `BranchSearchBudget`:
  - `max_candidates`: integer (default 3, minimum 1, maximum 3)
  - `max_refinements`: integer (default 1, minimum 0, maximum 1)
  - `estimated_cost_per_generation`: float (default 0.0 in offline mode)
- `BranchSearchResult`:
  - `state`: string (`succeeded`, `failed`, or `cancelled`)
  - `reason`: optional string
  - `winning_attempt`: optional `BranchAttempt`
  - `attempts`: list of `BranchAttempt`
  - `total_candidates_generated`: integer
  - `total_refinements_generated`: integer

**State transitions**:
1. START: Receive `RepairRequest`, `TaskRecipe`, `HostPorts`, `SandboxAdapter`, and `ModelAdapter`.
2. CHECK_SEARCH_MODE: If `request.search_mode` is `sequential`, execute sequential repair pipeline; if `branch_refine`, execute branch and refine search.
3. BASELINE_STAGE: Run baseline double check. If failed or cancelled, return terminal result.
4. UPGRADE_STAGE: Run dependency upgrade and failure reproduction. Capture immutable `checkpoint_id`. If failed or cancelled, return terminal result.
5. INIT_SEARCH: Initialize branch index = 1, attempts list = empty.
6. BRANCH_LOOP: While branch index <= `recipe.max_candidates` (at most 3):
   a. CHECK_CANCEL: Check `host.cancelled()`. If true, return `cancelled`.
   b. RESERVE_BUDGET: Call `host.reserve(f"branch_{branch_index}", cost)`. If false, return `failed` with reason `budget_exceeded`.
   c. GENERATE_BRANCH: Generate root candidate patch for branch index with prompt and extracted failure context.
   d. VALIDATE_PATCH: Validate patch paths and safety. If invalid, record failed attempt and advance to next branch.
   e. VERIFY_BRANCH: Provision fresh sandbox execution handle via `sandbox.create_execution(checkpoint_id)`. Run verifier with file hash checks, collection matching, and test execution. Persist attempt artifacts. Clean up execution handle.
   f. CHECK_SUCCESS: If verifier passed, return `succeeded` with winning attempt.
   g. EVALUATE_REFINEMENT: If verifier failed and refinement count for this branch < `recipe.max_refinements` (at most 1) and failure is actionable (test error or apply error):
      i. CHECK_CANCEL: Check `host.cancelled()`. If true, return `cancelled`.
      ii. RESERVE_BUDGET: Call `host.reserve(f"refine_{branch_index}_1", cost)`. If false, return `failed` with reason `budget_exceeded`.
      iii. GENERATE_REFINEMENT: Build refinement prompt including previous patch and failure logs. Call model.
      iv. VALIDATE_PATCH: Validate refined patch paths and safety. If invalid, record failed refinement attempt and advance.
      v. VERIFY_REFINEMENT: Provision fresh sandbox execution handle from checkpoint. Run verifier. Persist attempt artifacts. Clean up execution handle.
      vi. CHECK_SUCCESS: If refined verifier passed, return `succeeded` with winning refinement attempt.
   h. ADVANCE_BRANCH: Increment branch index by 1.
7. SEARCH_EXHAUSTED: If all branches and refinements failed, return `failed` with reason describing attempt counts.

**API surface**:
| Function or method | Scope | Key inputs | Key outputs | Auth | Key errors |
|---|---|---|---|---|---|
| `build_refinement_prompt(recipe, candidate, failure_output)` | Internal engine | `TaskRecipe`, `CandidatePatch`, string | string prompt | None | None |
| `generate_refinement_patch(recipe, candidate, failure_output, model, host, attempt_id, cost)` | Internal engine | `TaskRecipe`, `CandidatePatch`, string, `ModelAdapter`, `HostPorts`, string, float | `CandidatePatch` | None | `BudgetExceededError` |
| `run_branch_refine_search(request, recipe, host, sandbox, model, baseline, upgrade)` | Internal engine | `RepairRequest`, `TaskRecipe`, `HostPorts`, `SandboxAdapter`, `ModelAdapter`, `BaselineOutcome`, `UpgradeResult` | `RepairResult` | None | None |
| `repair(request, recipe, host, sandbox, model)` | Package entry point | `RepairRequest`, `TaskRecipe`, `HostPorts`, optional `SandboxAdapter`, optional `ModelAdapter` | `RepairResult` | None | None |

**Value sourcing**:
| Action | Value produced or displayed | Source |
|---|---|---|
| Search mode selection | Execution branch routing | `request.search_mode` matching literal `branch_refine` or `sequential` |
| Branch candidate identifier | String identifier | Generated deterministically as `candidate_{branch_index}` |
| Refinement candidate identifier | String identifier | Generated deterministically as `candidate_{branch_index}_refine_1` |
| Refinement prompt | Model prompt text | Combined recipe context, previous patch diff, and captured verification failure logs |
| Budget reservation | Host reservation confirmation | Return boolean of `host.reserve(operation_id, estimated_cost)` |
| Isolated execution handle | Clean sandbox instance | `sandbox.create_execution(checkpoint_id)` derived from upgrade checkpoint |
| Attempt artifacts | Saved artifact records | Unique attempt file names passed to `host.save_artifact` |
| Final repair state | Terminal state and reason | Composite outcome of branch search (`succeeded`, `failed`, or `cancelled`) |

**Key invariants**:
- The tree search never exceeds 3 root candidate branches and never exceeds 1 refinement per branch.
- Every candidate evaluation (root or refined) runs in a freshly provisioned sandbox handle derived from the immutable upgraded checkpoint.
- Refinement prompt explicitly includes the prior candidate diff and the failure message so the model knows what failed.
- The engine stops exploration immediately upon finding the first candidate that passes verification.
- Search never relies on model voting or heuristic guessing to override test verifier results.
- Cancellation is checked before each generation, before each verification, and before each refinement.
- Engine code never emits `run.finished` and never imports database models or HTTP routers.

**Security model**:
- All root patches and refined patches pass through `validate_patch` before any sandbox execution.
- Path traversal escapes, symlink escapes, and edits to test or config files are rejected immediately.
- Refinement prompts do not leak environment secrets or credentials.
- Execution handles are cleaned up in `finally` blocks to prevent resource leaks.

**Configuration required**:
- `REPOMEDIC_MODE`: defaults to `offline`.
- `REPOMEDIC_MAX_CANDIDATES`: defaults to 3 (caps tree branch width).
- `REPOMEDIC_MAX_REFINEMENTS`: defaults to 1 (caps branch refinement depth).
- `REPOMEDIC_MAX_OUTPUT_TOKENS`: defaults to 2048 for both candidate and refinement generation.

**Critical test scenarios**:
- First candidate passes: Engine generates candidate 1, verifies cleanly, terminates search immediately without generating candidate 2 or refinements, verifies AC-1, AC-3, AC-6, AC-8, AC-9.
- Refinement success: Candidate 1 fails verification, engine generates candidate 1 refinement 1 with failure feedback, refinement passes verification, search terminates with success without exploring branch 2, verifies AC-2, AC-3, AC-4, AC-6, AC-8, AC-9.
- Multi branch exploration: Candidate 1 and its refinement fail, engine advances to candidate 2 which passes verification, search succeeds, verifies AC-2, AC-3, AC-9, AC-10.
- All branches exhausted: All 3 candidates and their refinements fail verification, engine returns failed state with attempt summary, verifies AC-2, AC-10, AC-11.
- Budget reservation denial: Host denies budget reservation during branch 2 generation, search halts immediately with `budget_exceeded`, verifies AC-7.
- Mid search cancellation: Cancellation requested after candidate 1 fails verification, engine halts cleanly, cleans up sandbox, and returns `cancelled`, verifies AC-8.
- Patch safety rejection: Refined candidate attempts editing test files, rejected by validator before sandbox execution, verifies AC-5.
- Offline fake determinism: Entire tree search workflow runs offline using configurable presets in fake adapters with zero network spend, verifies AC-12.

## Build plan

- [x] 1. Define branch search data models and outcome structures in `backend/src/engine/candidate.py` (`BranchAttempt`, `BranchSearchResult`, `BranchSearchBudget`), satisfies AC-1, AC-2
- [x] 2. Implement refinement prompt builder in `backend/src/engine/candidate_generator.py` incorporating prior patch and verifier failure output, satisfies AC-4
- [x] 3. Implement refinement patch generator in `backend/src/engine/candidate_generator.py` with budget reservation and 2048 token cap, satisfies AC-4, AC-7
- [x] 4. Implement branch and refine search coordinator in `backend/src/engine/branch_search.py` managing depth first traversal, early stopping, fresh sandbox provisioning, and cancellation, satisfies AC-2, AC-3, AC-6, AC-8, AC-9, AC-10, AC-11
- [x] 5. Update `repair()` in `backend/src/engine/repair.py` to route between sequential repair and branch refine search based on `request.search_mode`, satisfies AC-1
- [x] 6. Enhance `FakeModelAdapter` in `backend/src/engine/fake_model.py` with multi response sequencing and refinement presets to support tree search testing, satisfies AC-12
- [x] 7. Enhance `FakeSandboxAdapter` in `backend/src/engine/fake_sandbox.py` with per candidate execution tracking and multi attempt presets, satisfies AC-6, AC-12
- [x] 8. Add comprehensive unit tests in `backend/tests/engine/test_branch_refine.py` covering first candidate pass, refinement pass, branch fallback, budget exhaustion, cancellation, and safety rejections, satisfies AC-1 through AC-12

## Consequences

**Positive**:
- Significantly increases repair success rate on challenging bugs by exploring alternate hypotheses and learning from failed verification attempts.
- Enforces hard boundaries (maximum 3 branches, maximum 1 refinement) preventing runaway token usage or infinite repair loops.
- Depth first search with early stopping minimizes latency and token cost on easier repairs.
- Keeps sandbox execution isolated across all attempts, ensuring zero cross candidate contamination.

**Negative / tradeoffs**:
- Worst case execution time and token consumption increases up to sixfold when all candidates and refinements are evaluated.
- Additional artifact persistence calls per attempt increase host storage metadata volume.

**Neutral**:
- Fully backwards compatible with existing sequential repair mode and shared contracts.
- Seamlessly prepares for live provider adapters in checkpoint K4.

## Follow-up

- [ ] Checkpoint K4: Connect live Nebius Token Factory model adapter with temperature variation across branches.
- [ ] Checkpoint K4: Map fresh sandbox execution handle creation to live Nebius sandbox snapshots or container forks.
- [ ] Slice D coordination: Ensure evaluation metrics capture branch count and refinement depth in benchmark summaries.

## Rationale

Reasoning, alternatives considered, and tradeoffs: see rationale.md
