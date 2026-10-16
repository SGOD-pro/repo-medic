import pytest
from src.contracts import RepairRequest, TaskRecipe
from src.engine.adapters import SandboxPreset
from src.engine.branch_search import run_branch_refine_search
from src.engine.candidate import (
    BranchSearchBudget,
    BranchSearchResult,
    CandidatePatch,
    UpgradeResult,
)
from src.engine.candidate_generator import (
    build_refinement_prompt,
    generate_refinement_patch,
)
from src.engine.fake_model import (
    DEFAULT_VALID_PATCH,
    REFINED_VALID_PATCH,
    SECOND_BRANCH_VALID_PATCH,
    UNSAFE_TEST_PATCH,
    UNSAFE_TRAVERSAL_PATCH,
    FakeModelAdapter,
)
from src.engine.fake_sandbox import FakeSandboxAdapter
from src.engine.repair import repair
from src.storage.fake_host import FakeHost


@pytest.fixture
def branch_recipe() -> TaskRecipe:
    return TaskRecipe(
        task_id="branch-task-1",
        title="Upgrade package from 1.0.0 to 2.0.0 with branch and refine",
        repository_url="https://github.com/example/repo",
        commit_sha="123456abcdef",
        dependency="example-lib",
        from_version="1.0.0",
        to_version="2.0.0",
        test_command=["pytest", "tests/"],
        allowed_source_paths=["src/"],
        expected_failure="AssertionError",
        timeout_seconds=60,
        max_candidates=3,
        max_refinements=1,
    )


@pytest.fixture
def branch_request() -> RepairRequest:
    return RepairRequest(
        run_id="run-branch-1",
        task_id="branch-task-1",
        mode="offline",
        search_mode="branch_refine",
        max_run_usd=1.0,
    )


# --- AC-1: Search Mode Routing ---
@pytest.mark.asyncio
async def test_repair_routes_sequential_vs_branch_refine(
    branch_recipe: TaskRecipe,
):
    host = FakeHost()
    sandbox = FakeSandboxAdapter(preset=SandboxPreset.SUCCESS)
    model = FakeModelAdapter()

    # 1. Sequential search mode
    seq_request = RepairRequest(
        run_id="run-seq",
        task_id="branch-task-1",
        mode="offline",
        search_mode="sequential",
        max_run_usd=1.0,
    )
    seq_result = await repair(seq_request, branch_recipe, host, sandbox=sandbox, model=model)
    assert seq_result.state == "succeeded"
    assert model.call_count == 1

    # 2. Branch refine search mode
    branch_request = RepairRequest(
        run_id="run-br",
        task_id="branch-task-1",
        mode="offline",
        search_mode="branch_refine",
        max_run_usd=1.0,
    )
    host2 = FakeHost()
    sandbox2 = FakeSandboxAdapter(preset=SandboxPreset.SUCCESS)
    model2 = FakeModelAdapter()
    branch_result = await repair(branch_request, branch_recipe, host2, sandbox=sandbox2, model=model2)
    assert branch_result.state == "succeeded"
    assert model2.call_count == 1


# --- AC-3 & AC-9: First Candidate Passes (Early Stopping) ---
@pytest.mark.asyncio
async def test_first_candidate_passes_early_stopping(
    branch_request: RepairRequest, branch_recipe: TaskRecipe
):
    host = FakeHost()
    sandbox = FakeSandboxAdapter(preset=SandboxPreset.SUCCESS)
    model = FakeModelAdapter()

    result = await repair(branch_request, branch_recipe, host, sandbox=sandbox, model=model)

    assert result.state == "succeeded"
    assert "candidate_1" in (result.reason or "")
    # Should stop on candidate 1 without generating candidate 2 or 3
    assert model.call_count == 1

    candidate_events = [e for e in host.events if e["type"] == "candidate.completed"]
    assert len(candidate_events) == 1
    assert candidate_events[0]["payload"]["candidate_id"] == "candidate_1"
    assert candidate_events[0]["payload"]["passed"] is True

    # Invariants: exactly one stage.completed for verification, never run.finished
    stage_events = [e for e in host.events if e["type"] == "stage.completed"]
    verify_events = [e for e in stage_events if e["payload"]["stage"] == "verification"]
    assert len(verify_events) == 1
    assert verify_events[0]["payload"]["passed"] is True
    assert not any(e["type"] == "run.finished" for e in host.events)


# --- AC-3, AC-4, AC-9: Refinement Pass (Depth First) ---
@pytest.mark.asyncio
async def test_refinement_pass_recovers_failed_candidate(
    branch_request: RepairRequest, branch_recipe: TaskRecipe
):
    host = FakeHost()
    # First execution handle fails test, second execution handle (refinement) passes!
    sandbox = FakeSandboxAdapter(
        execution_presets=[SandboxPreset.VERIFY_TEST_FAIL, SandboxPreset.SUCCESS]
    )
    # Model returns initial patch, then refined patch
    model = FakeModelAdapter(
        canned_responses=[DEFAULT_VALID_PATCH, REFINED_VALID_PATCH]
    )

    result = await repair(branch_request, branch_recipe, host, sandbox=sandbox, model=model)

    assert result.state == "succeeded"
    assert "candidate_1_refine_1" in (result.reason or "")
    # Exactly 2 model calls: candidate 1 and candidate 1 refinement 1
    assert model.call_count == 2

    # Verification events: candidate_1 fails, candidate_1_refine_1 passes
    candidate_events = [e for e in host.events if e["type"] == "candidate.completed"]
    assert len(candidate_events) == 2
    assert candidate_events[0]["payload"]["candidate_id"] == "candidate_1"
    assert candidate_events[0]["payload"]["passed"] is False
    assert candidate_events[1]["payload"]["candidate_id"] == "candidate_1_refine_1"
    assert candidate_events[1]["payload"]["passed"] is True

    # Exactly 1 verification stage event reflecting overall success
    stage_events = [e for e in host.events if e["type"] == "stage.completed"]
    verify_events = [e for e in stage_events if e["payload"]["stage"] == "verification"]
    assert len(verify_events) == 1
    assert verify_events[0]["payload"]["passed"] is True


# --- AC-4: Refinement Prompt Structure ---
def test_build_refinement_prompt_structure(branch_recipe: TaskRecipe):
    prev_candidate = CandidatePatch(
        candidate_id="candidate_1",
        diff_content="--- a/src/app.py\n+++ b/src/app.py\n@@ -1 +1 @@\n-def fix(): False\n+def fix(): None\n",
        modified_files=["src/app.py"],
    )
    failure_log = "AssertionError: expected True but got None at test_app.py:10"

    prompt = build_refinement_prompt(branch_recipe, prev_candidate, failure_log)

    assert "Previous Candidate Patch (candidate_1)" in prompt
    assert prev_candidate.diff_content in prompt
    assert "Verification Failure Observed" in prompt
    assert failure_log in prompt
    assert branch_recipe.dependency in prompt


# --- AC-2, AC-3: Multi Branch Fallback ---
@pytest.mark.asyncio
async def test_multi_branch_exploration_after_refinement_failure(
    branch_request: RepairRequest, branch_recipe: TaskRecipe
):
    host = FakeHost()
    # Branch 1 fails, Refinement 1 fails, Branch 2 succeeds!
    sandbox = FakeSandboxAdapter(
        execution_presets=[
            SandboxPreset.VERIFY_TEST_FAIL,  # candidate 1
            SandboxPreset.VERIFY_TEST_FAIL,  # candidate 1 refine 1
            SandboxPreset.SUCCESS,           # candidate 2
        ]
    )
    model = FakeModelAdapter(
        canned_responses=[
            DEFAULT_VALID_PATCH,        # candidate 1
            REFINED_VALID_PATCH,        # candidate 1 refine 1
            SECOND_BRANCH_VALID_PATCH,  # candidate 2
        ]
    )

    result = await repair(branch_request, branch_recipe, host, sandbox=sandbox, model=model)

    assert result.state == "succeeded"
    assert "candidate_2" in (result.reason or "")
    assert model.call_count == 3

    candidate_events = [e for e in host.events if e["type"] == "candidate.completed"]
    assert len(candidate_events) == 3
    assert candidate_events[0]["payload"]["candidate_id"] == "candidate_1"
    assert candidate_events[1]["payload"]["candidate_id"] == "candidate_1_refine_1"
    assert candidate_events[2]["payload"]["candidate_id"] == "candidate_2"
    assert candidate_events[2]["payload"]["passed"] is True


# --- AC-2, AC-11: Exhaustion of All Branches and Refinements ---
@pytest.mark.asyncio
async def test_exhaustion_when_all_branches_and_refinements_fail(
    branch_request: RepairRequest, branch_recipe: TaskRecipe
):
    host = FakeHost()
    # All 6 executions fail (3 candidates + 3 refinements)
    sandbox = FakeSandboxAdapter(
        execution_presets=[SandboxPreset.VERIFY_TEST_FAIL] * 6
    )
    model = FakeModelAdapter()

    result = await repair(branch_request, branch_recipe, host, sandbox=sandbox, model=model)

    assert result.state == "failed"
    assert "failed" in (result.reason or "").lower()
    assert model.call_count == 6

    # Overall stage.completed verification event must be passed=False
    stage_events = [e for e in host.events if e["type"] == "stage.completed"]
    verify_events = [e for e in stage_events if e["payload"]["stage"] == "verification"]
    assert len(verify_events) == 1
    assert verify_events[0]["payload"]["passed"] is False

    # Never emit run.finished
    assert not any(e["type"] == "run.finished" for e in host.events)


# --- AC-5: Patch Safety Rejection Skips Refinement ---
@pytest.mark.asyncio
async def test_unsafe_patch_rejected_and_skips_refinement(
    branch_request: RepairRequest, branch_recipe: TaskRecipe
):
    host = FakeHost()
    sandbox = FakeSandboxAdapter(preset=SandboxPreset.SUCCESS)
    # Branch 1 produces unsafe traversal patch, Branch 2 produces clean patch
    model = FakeModelAdapter(
        canned_responses=[UNSAFE_TRAVERSAL_PATCH, DEFAULT_VALID_PATCH]
    )

    result = await repair(branch_request, branch_recipe, host, sandbox=sandbox, model=model)

    assert result.state == "succeeded"
    assert "candidate_2" in (result.reason or "")
    # Candidate 1 was rejected by validator, skipped refinement, proceeded to candidate 2!
    assert model.call_count == 2

    candidate_events = [e for e in host.events if e["type"] == "candidate.completed"]
    assert len(candidate_events) == 2
    assert candidate_events[0]["payload"]["candidate_id"] == "candidate_1"
    assert candidate_events[0]["payload"]["passed"] is False
    summary0 = candidate_events[0]["payload"]["summary"].lower()
    assert "forbidden path" in summary0 or "traversal" in summary0
    assert candidate_events[1]["payload"]["candidate_id"] == "candidate_2"
    assert candidate_events[1]["payload"]["passed"] is True


# --- AC-6: Clean Sandbox Isolation and Resource Cleanup ---
@pytest.mark.asyncio
async def test_fresh_sandbox_execution_and_cleanup_per_attempt(
    branch_request: RepairRequest, branch_recipe: TaskRecipe
):
    host = FakeHost()
    sandbox = FakeSandboxAdapter(
        execution_presets=[SandboxPreset.VERIFY_TEST_FAIL, SandboxPreset.SUCCESS]
    )
    model = FakeModelAdapter(
        canned_responses=[DEFAULT_VALID_PATCH, REFINED_VALID_PATCH]
    )

    result = await repair(branch_request, branch_recipe, host, sandbox=sandbox, model=model)

    assert result.state == "succeeded"
    # Exactly 2 execution handles provisioned from checkpoint
    assert len(sandbox.execution_handles) == 2
    # Both handles must have cleanup() called
    for handle in sandbox.execution_handles:
        assert handle.is_execution_handle is True
        assert handle.cleaned_up is True


# --- AC-7: Budget Reservation Denial ---
class BudgetDenyingHost(FakeHost):
    def __init__(self, deny_after_n_reserves: int = 0):
        super().__init__()
        self.deny_after = deny_after_n_reserves
        self.reserve_count = 0

    async def reserve(self, operation_id: str, estimated_usd: float) -> bool:
        self.reserve_count += 1
        if self.reserve_count > self.deny_after:
            return False
        return await super().reserve(operation_id, estimated_usd)


@pytest.mark.asyncio
async def test_budget_reservation_denial_halts_search(
    branch_request: RepairRequest, branch_recipe: TaskRecipe
):
    # Host denies first reservation attempt
    host = BudgetDenyingHost(deny_after_n_reserves=0)
    sandbox = FakeSandboxAdapter(preset=SandboxPreset.SUCCESS)
    model = FakeModelAdapter()

    # Budget configured with cost > 0
    budget = BranchSearchBudget(max_candidates=3, max_refinements=1, estimated_cost_per_generation=0.05)

    upgrade_res = UpgradeResult(success=True, checkpoint_id="chk_up")
    result = await run_branch_refine_search(
        request=branch_request,
        recipe=branch_recipe,
        host=host,
        sandbox=sandbox,
        model=model,
        upgrade=upgrade_res,
        budget=budget,
    )

    assert result.state == "failed"
    assert "Budget reservation" in (result.reason or "")
    assert "denied" in (result.reason or "")
    # Model complete must not have been invoked
    assert model.call_count == 0


# --- AC-8: Cancellation Checks ---
class CancelledHost(FakeHost):
    def __init__(self, cancel_after_n_checks: int = 1):
        super().__init__()
        self.cancel_after = cancel_after_n_checks
        self.check_count = 0

    async def cancelled(self) -> bool:
        self.check_count += 1
        return self.check_count >= self.cancel_after


@pytest.mark.asyncio
async def test_cancellation_during_branch_search(
    branch_request: RepairRequest, branch_recipe: TaskRecipe
):
    # Cancelled after baseline and upgrade
    host = CancelledHost(cancel_after_n_checks=3)
    sandbox = FakeSandboxAdapter(preset=SandboxPreset.SUCCESS)
    model = FakeModelAdapter()

    result = await repair(branch_request, branch_recipe, host, sandbox=sandbox, model=model)

    assert result.state == "cancelled"
    assert "cancelled" in (result.reason or "").lower()


@pytest.mark.asyncio
async def test_branch_search_cancels_before_accepting_results(
    branch_request: RepairRequest, branch_recipe: TaskRecipe
):
    host = FakeHost()
    sandbox = FakeSandboxAdapter(preset=SandboxPreset.SUCCESS)
    model = FakeModelAdapter()

    check_count = 0

    async def cancel_on_verification_accept():
        nonlocal check_count
        check_count += 1
        # Cancel right after verification of candidate passes
        return check_count >= 5

    host.cancelled = cancel_on_verification_accept  # type: ignore

    result = await repair(branch_request, branch_recipe, host, sandbox=sandbox, model=model)
    assert result.state == "cancelled"
    assert "cancelled" in (result.reason or "").lower()


# --- AC-10: Evidence and Artifact Preservation Per Attempt ---
@pytest.mark.asyncio
async def test_attempt_scoped_and_canonical_artifact_saving(
    branch_request: RepairRequest, branch_recipe: TaskRecipe
):
    host = FakeHost()
    # Candidate 1 fails, Refinement 1 succeeds
    sandbox = FakeSandboxAdapter(
        execution_presets=[SandboxPreset.VERIFY_TEST_FAIL, SandboxPreset.SUCCESS]
    )
    model = FakeModelAdapter(
        canned_responses=[DEFAULT_VALID_PATCH, REFINED_VALID_PATCH]
    )

    result = await repair(branch_request, branch_recipe, host, sandbox=sandbox, model=model)
    assert result.state == "succeeded"

    filenames = [a["filename"] for a in host.artifacts]

    # Candidate 1 attempt artifacts preserved
    assert "candidate_1_patch.diff" in filenames
    assert "candidate_1_verify.log" in filenames
    assert "candidate_1_evidence.json" in filenames

    # Refinement 1 attempt artifacts preserved
    assert "candidate_1_refine_1_patch.diff" in filenames
    assert "candidate_1_refine_1_verify.log" in filenames
    assert "candidate_1_refine_1_evidence.json" in filenames

    # Canonical artifacts saved for winning attempt
    assert "patch.diff" in filenames
    assert "verify.log" in filenames
    assert "evidence.json" in filenames


# --- Refinement Generation Error Handling & Branch Advancement ---
class ErrorOnRefinementModel(FakeModelAdapter):
    def __init__(self):
        super().__init__()
        self.call_idx = 0

    async def complete(self, prompt: str, max_tokens: int = 2048) -> str:
        self.call_count += 1
        self.prompts.append(prompt)
        self.call_idx += 1
        if self.call_idx == 1:
            return DEFAULT_VALID_PATCH
        elif self.call_idx == 2:
            raise RuntimeError("Transient adapter inference timeout")
        else:
            return SECOND_BRANCH_VALID_PATCH


@pytest.mark.asyncio
async def test_refinement_generation_error_recorded_and_advances_to_next_branch(
    branch_request: RepairRequest, branch_recipe: TaskRecipe
):
    host = FakeHost()
    sandbox = FakeSandboxAdapter(
        execution_presets=[SandboxPreset.VERIFY_TEST_FAIL, SandboxPreset.SUCCESS]
    )
    model = ErrorOnRefinementModel()

    result = await repair(branch_request, branch_recipe, host, sandbox=sandbox, model=model)

    assert result.state == "succeeded"
    assert "candidate_2" in (result.reason or "")

    candidate_events = [e for e in host.events if e["type"] == "candidate.completed"]
    assert len(candidate_events) == 3
    refine_event = candidate_events[1]
    assert refine_event["payload"]["candidate_id"] == "candidate_1_refine_1"
    assert refine_event["payload"]["passed"] is False
    assert "Refinement generation error" in refine_event["payload"]["summary"]


# --- Direct BranchSearchResult Structure Verification ---
@pytest.mark.asyncio
async def test_branch_search_returns_branch_search_result_with_attempts(
    branch_request: RepairRequest, branch_recipe: TaskRecipe
):
    host = FakeHost()
    sandbox = FakeSandboxAdapter(
        execution_presets=[SandboxPreset.VERIFY_TEST_FAIL, SandboxPreset.SUCCESS]
    )
    model = FakeModelAdapter(
        canned_responses=[DEFAULT_VALID_PATCH, REFINED_VALID_PATCH]
    )
    upgrade_res = UpgradeResult(success=True, checkpoint_id="chk_up")

    search_result = await run_branch_refine_search(
        request=branch_request,
        recipe=branch_recipe,
        host=host,
        sandbox=sandbox,
        model=model,
        upgrade=upgrade_res,
    )

    assert isinstance(search_result, BranchSearchResult)
    assert search_result.state == "succeeded"
    assert search_result.winning_attempt is not None
    assert search_result.winning_attempt.attempt_id == "candidate_1_refine_1"
    assert search_result.total_candidates_generated == 1
    assert search_result.total_refinements_generated == 1
    assert len(search_result.attempts) == 2


# --- Review Polish Verifications ---
@pytest.mark.asyncio
async def test_max_candidates_lower_bound_clamped_to_one(
    branch_request: RepairRequest, branch_recipe: TaskRecipe
):
    host = FakeHost()
    sandbox = FakeSandboxAdapter(preset=SandboxPreset.SUCCESS)
    model = FakeModelAdapter()
    upgrade_res = UpgradeResult(success=True, checkpoint_id="chk_up")

    # Recipe specifies 0 or negative max_candidates
    recipe_zero_candidates = TaskRecipe(
        task_id=branch_recipe.task_id,
        title=branch_recipe.title,
        repository_url=branch_recipe.repository_url,
        commit_sha=branch_recipe.commit_sha,
        dependency=branch_recipe.dependency,
        from_version=branch_recipe.from_version,
        to_version=branch_recipe.to_version,
        test_command=branch_recipe.test_command,
        allowed_source_paths=branch_recipe.allowed_source_paths,
        expected_failure=branch_recipe.expected_failure,
        timeout_seconds=branch_recipe.timeout_seconds,
        max_candidates=0,
        max_refinements=branch_recipe.max_refinements,
    )

    search_result = await run_branch_refine_search(
        request=branch_request,
        recipe=recipe_zero_candidates,
        host=host,
        sandbox=sandbox,
        model=model,
        upgrade=upgrade_res,
    )

    assert search_result.state == "succeeded"
    assert search_result.total_candidates_generated == 1


def test_engine_package_exports_refinement_functions():
    import src.engine as engine

    assert hasattr(engine, "generate_refinement_patch")
    assert callable(engine.generate_refinement_patch)
    assert hasattr(engine, "build_refinement_prompt")
    assert callable(engine.build_refinement_prompt)
    assert "generate_refinement_patch" in engine.__all__
    assert "build_refinement_prompt" in engine.__all__
