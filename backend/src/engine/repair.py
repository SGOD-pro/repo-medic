from typing import Optional
from src.contracts import HostPorts, RepairRequest, RepairResult, TaskRecipe
from src.engine.adapters import ModelAdapter, SandboxAdapter
from src.engine.baseline import run_baseline_stage
from src.engine.branch_search import run_branch_refine_search
from src.engine.candidate_generator import BudgetExceededError, generate_candidate_patch
from src.engine.fake_model import FakeModelAdapter
from src.engine.fake_sandbox import FakeSandboxAdapter
from src.engine.patch_validator import validate_patch
from src.engine.upgrade import run_upgrade_stage
from src.engine.validation import RecipeValidationError, validate_recipe
from src.engine.verifier import verify_candidate_patch


async def repair(
    request: RepairRequest,
    recipe: TaskRecipe,
    host: HostPorts,
    sandbox: Optional[SandboxAdapter] = None,
    model: Optional[ModelAdapter] = None,
) -> RepairResult:
    """
    Main engine entry point for task repair.
    Coordinates sequential pipeline:
    1. Task recipe validation
    2. Baseline double-check verification
    3. Dependency upgrade and expected failure reproduction
    4. Model candidate patch generation with token bounds
    5. Patch safety validation against allowed source paths
    6. Candidate verification in isolated sandbox
    """
    # 1. Validate recipe bounds and invariants
    try:
        validate_recipe(recipe)
    except RecipeValidationError as exc:
        return RepairResult(state="failed", reason=f"Recipe validation failed: {exc}")

    # 2. Check early cancellation
    if await host.cancelled():
        return RepairResult(state="cancelled", reason="User cancelled before execution")

    # 3. Resolve adapters (default to deterministic fakes in offline mode)
    active_sandbox = sandbox or FakeSandboxAdapter()
    active_model = model or FakeModelAdapter()

    # 4. Run baseline verification stage
    baseline = await run_baseline_stage(recipe, active_sandbox, host)
    if baseline.cancelled:
        return RepairResult(state="cancelled", reason=baseline.summary)
    if not baseline.passed:
        return RepairResult(state="failed", reason=baseline.summary)

    # 5. Check cancellation before upgrade
    if await host.cancelled():
        return RepairResult(state="cancelled", reason="User cancelled after baseline stage")

    # 6. Run dependency upgrade stage
    upgrade = await run_upgrade_stage(recipe, active_sandbox, host)
    if not upgrade.success:
        return RepairResult(state="failed", reason=upgrade.summary)

    # 7. Check cancellation before repair search
    if await host.cancelled():
        return RepairResult(state="cancelled", reason="User cancelled after upgrade stage")

    # 8. Route by search mode: branch and refine vs sequential
    if request.search_mode == "branch_refine":
        search_result = await run_branch_refine_search(
            request=request,
            recipe=recipe,
            host=host,
            sandbox=active_sandbox,
            model=active_model,
            upgrade=upgrade,
            baseline_collected_count=baseline.collected_count,
            baseline_preservation=baseline.preservation,
            checkpoint_id=upgrade.checkpoint_id,
            mode=request.mode,
        )
        return RepairResult(state=search_result.state, reason=search_result.reason)

    # 9. Generate candidate patch
    try:
        candidate = await generate_candidate_patch(
            recipe=recipe,
            upgrade=upgrade,
            model=active_model,
            host=host,
            candidate_id="candidate_1",
            estimated_cost=0.0,
        )
    except BudgetExceededError as exc:
        return RepairResult(state="failed", reason=str(exc))
    except Exception as exc:
        return RepairResult(state="failed", reason=f"Candidate generation error: {exc}")

    # 10. Validate patch safety against allowed source paths
    patch_validation = validate_patch(candidate.diff_content, recipe)
    if not patch_validation.valid:
        await host.emit(
            "candidate.completed",
            {
                "candidate_id": candidate.candidate_id,
                "passed": False,
                "summary": patch_validation.reason,
            },
        )
        await host.emit(
            "stage.completed",
            {"stage": "verification", "passed": False, "summary": patch_validation.reason},
        )
        return RepairResult(state="failed", reason=patch_validation.reason)

    # 11. Check cancellation before candidate verification
    if await host.cancelled():
        return RepairResult(state="cancelled", reason="User cancelled before verification")

    # 12. Verify candidate patch in clean sandbox
    verification = await verify_candidate_patch(
        candidate=candidate,
        recipe=recipe,
        sandbox=active_sandbox,
        host=host,
        baseline_collected_count=baseline.collected_count,
        baseline_preservation=baseline.preservation,
        checkpoint_id=upgrade.checkpoint_id,
        mode=request.mode,
    )
    if not verification.passed:
        return RepairResult(state="failed", reason=verification.summary)

    # 13. Clean sequential repair succeeded
    return RepairResult(
        state="succeeded",
        reason="Candidate verified cleanly and resolved upgrade regression",
    )
