import logging
import os
from typing import Dict, Optional
from src.config import settings
from src.contracts import HostPorts, RepairRequest, RepairResult, TaskRecipe
from src.engine.adapters import ModelAdapter, SandboxAdapter
from src.engine.baseline import run_baseline_stage
from src.engine.branch_search import run_branch_refine_search
from src.engine.candidate import BranchSearchBudget
from src.engine.candidate_generator import (
    BudgetExceededError,
    collect_target_source_files,
    generate_candidate_patch,
)
from src.engine.contree_sandbox import ConTreeSandboxAdapter
from src.engine.extraction import extract_error_context
from src.engine.fake_model import FakeModelAdapter, get_canned_patch_for_recipe
from src.engine.fake_sandbox import FakeSandboxAdapter
from src.engine.patch_validator import validate_patch
from src.engine.token_factory_model import TokenFactoryModelAdapter
from src.engine.upgrade import run_upgrade_stage
from src.engine.validation import RecipeValidationError, validate_recipe
from src.engine.verifier import verify_candidate_patch

logger = logging.getLogger("repomedic.repair")


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
    2. Baseline double check verification
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

    # 3. Resolve adapters (explicit live selection with zero fake fallback)
    owned_sandbox = False
    if request.mode == "live":
        nebius_key = (
            (getattr(sandbox, "api_key", None))
            or settings.nebius_api_key
            or ""
        ).strip()
        project_id = (
            (getattr(sandbox, "project_id", None))
            or settings.nebius_project_id
            or ""
        ).strip()
        missing = []
        if not nebius_key:
            missing.append("NEBIUS_API_KEY")
        if not project_id:
            missing.append("NEBIUS_PROJECT_ID")
        if missing:
            return RepairResult(
                state="failed",
                reason=f"Live execution halted: missing required credentials: {', '.join(missing)}",
            )

        if sandbox is not None:
            active_sandbox = sandbox
        else:
            active_sandbox = ConTreeSandboxAdapter(
                api_key=nebius_key,
                project_id=project_id,
                base_image=settings.nebius_sandbox_image or "python:3.12-bookworm",
                timeout_seconds=600,
            )
            owned_sandbox = True

        if model is not None:
            active_model = model
        else:
            active_model = TokenFactoryModelAdapter(
                api_key=nebius_key,
                base_url=settings.token_factory_base_url,
                model=settings.token_factory_model,
            )
    else:
        active_sandbox = sandbox or FakeSandboxAdapter(reproduced_failure_stderr=recipe.expected_failure)
        if model is not None:
            active_model = model
        else:
            canned = get_canned_patch_for_recipe(recipe)
            if canned is not None:
                active_model = FakeModelAdapter(canned_response=canned)
            else:
                return RepairResult(
                    state="failed",
                    reason=(
                        f"Offline simulation does not support task '{recipe.task_id}'. "
                        "Live execution mode with Nebius provider is required for un-cached repositories."
                    ),
                )

    reserved_setup = False
    try:
        # Reserve setup budget if in live mode
        if request.mode == "live":
            reserved_setup = await host.reserve("sandbox:setup", 0.20)
            if not reserved_setup:
                return RepairResult(
                    state="failed",
                    reason="Budget reservation of $0.20 for sandbox setup denied by host",
                )

        # Prepare repository in sandbox if supported
        if hasattr(active_sandbox, "prepare_repository") and callable(active_sandbox.prepare_repository):
            try:
                await active_sandbox.prepare_repository(recipe)
            except Exception as exc:
                return RepairResult(
                    state="failed",
                    reason=f"Repository preparation failed: {exc}",
                )

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

        # Settle setup budget
        if reserved_setup:
            await host.settle("sandbox:setup", 0.20)
            reserved_setup = False

        # If automatic regression discovery detected no failure under target version, finish cleanly
        if getattr(upgrade, "no_regression_detected", False):
            return RepairResult(
                state="succeeded",
                reason=f"No regression detected: test suite passed cleanly under target version {recipe.to_version}",
            )

        # 7. Check cancellation before repair search
        if await host.cancelled():
            return RepairResult(state="cancelled", reason="User cancelled after upgrade stage")

        # 8. Route by search mode: branch and refine vs sequential
        if request.search_mode == "branch_refine":
            gen_cost = 0.05 if request.mode == "live" else 0.0
            search_budget = BranchSearchBudget(
                max_candidates=recipe.max_candidates or 3,
                max_refinements=recipe.max_refinements or 1,
                estimated_cost_per_generation=gen_cost,
            )
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
                budget=search_budget,
            )
            return RepairResult(state=search_result.state, reason=search_result.reason)

        # 9. Read source files for allowed paths from sandbox to provide accurate context
        source_files = await collect_target_source_files(recipe, upgrade.failure_output, active_sandbox)

        # Generate candidate patch
        try:
            candidate = await generate_candidate_patch(
                recipe=recipe,
                upgrade=upgrade,
                model=active_model,
                host=host,
                candidate_id="candidate_1",
                estimated_cost=0.05,
                source_files=source_files,
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

        # 13. Check cancellation before accepting repair results
        if await host.cancelled():
            return RepairResult(
                state="cancelled",
                reason="User cancelled after verification before accepting results",
            )

        # 14. Clean sequential repair succeeded
        return RepairResult(
            state="succeeded",
            reason="Candidate verified cleanly and resolved upgrade regression",
        )
    finally:
        if reserved_setup:
            try:
                await host.settle("sandbox:setup", 0.20)
            except Exception:
                pass
        if owned_sandbox and hasattr(active_sandbox, "cleanup") and callable(active_sandbox.cleanup):
            try:
                await active_sandbox.cleanup()
            except Exception:
                pass
