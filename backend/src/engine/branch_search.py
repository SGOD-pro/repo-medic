import time
from typing import List, Optional
from src.contracts import HostPorts, RepairRequest, TaskRecipe
from src.engine.adapters import ModelAdapter, SandboxAdapter
from src.engine.candidate import (
    BranchAttempt,
    BranchSearchBudget,
    BranchSearchResult,
    CandidatePatch,
    TestPreservationRecord,
    UpgradeResult,
)
from src.engine.candidate_generator import (
    BudgetExceededError,
    generate_candidate_patch,
    generate_refinement_patch,
)
from src.engine.patch_validator import validate_patch
from src.engine.verifier import save_canonical_artifacts, verify_candidate_patch


async def run_branch_refine_search(
    request: RepairRequest,
    recipe: TaskRecipe,
    host: HostPorts,
    sandbox: SandboxAdapter,
    model: ModelAdapter,
    upgrade: UpgradeResult,
    baseline_collected_count: int = 0,
    baseline_preservation: Optional[TestPreservationRecord] = None,
    checkpoint_id: str = "chk_upgrade",
    mode: str = "offline",
    budget: Optional[BranchSearchBudget] = None,
) -> BranchSearchResult:
    """
    Coordinates bounded depth first branch and refine repair search:
    1. Explores up to 3 candidate branches (capped by recipe.max_candidates).
    2. Allows at most 1 refinement per candidate branch upon verification failure.
    3. Performs depth first scheduling: attempts immediate refinement before moving to next branch.
    4. Enforces budget reservations and cancellation checks before every generation/verification.
    5. Verifies every attempt in an isolated execution handle created from the upgraded checkpoint.
    6. Stops immediately upon the first verified fix, persisting evidence for all attempts.
    """
    search_budget = budget or BranchSearchBudget(
        max_candidates=max(1, min(recipe.max_candidates if recipe.max_candidates is not None else 3, 3)),
        max_refinements=min(recipe.max_refinements if recipe.max_refinements is not None else 1, 1),
    )

    attempts: List[BranchAttempt] = []
    total_candidates = 0
    total_refinements = 0

    for branch_idx in range(1, search_budget.max_candidates + 1):
        # 1. Check cancellation before branch generation
        if await host.cancelled():
            return BranchSearchResult(
                state="cancelled",
                reason=f"User cancelled during branch search before candidate {branch_idx}",
                attempts=attempts,
                total_candidates_generated=total_candidates,
                total_refinements_generated=total_refinements,
            )

        candidate_id = f"candidate_{branch_idx}"
        total_candidates += 1
        start_gen = time.monotonic()

        # 2. Generate root branch candidate patch
        try:
            candidate = await generate_candidate_patch(
                recipe=recipe,
                upgrade=upgrade,
                model=model,
                host=host,
                candidate_id=candidate_id,
                estimated_cost=search_budget.estimated_cost_per_generation,
            )
        except BudgetExceededError as exc:
            return BranchSearchResult(
                state="failed",
                reason=str(exc),
                attempts=attempts,
                total_candidates_generated=total_candidates,
                total_refinements_generated=total_refinements,
            )
        except Exception as exc:
            return BranchSearchResult(
                state="failed",
                reason=f"Candidate generation error for {candidate_id}: {exc}",
                attempts=attempts,
                total_candidates_generated=total_candidates,
                total_refinements_generated=total_refinements,
            )

        # 3. Validate patch safety
        validation = validate_patch(candidate.diff_content, recipe)
        if not validation.valid:
            await host.emit(
                "candidate.completed",
                {
                    "candidate_id": candidate_id,
                    "passed": False,
                    "summary": validation.reason,
                },
            )
            attempts.append(
                BranchAttempt(
                    attempt_id=candidate_id,
                    branch_index=branch_idx,
                    is_refinement=False,
                    patch=candidate,
                    validation=validation,
                    duration_seconds=time.monotonic() - start_gen,
                )
            )
            # Patch safety rejection skips refinement; proceed to next branch
            continue

        # 4. Check cancellation before branch verification
        if await host.cancelled():
            return BranchSearchResult(
                state="cancelled",
                reason=f"User cancelled before verification of {candidate_id}",
                attempts=attempts,
                total_candidates_generated=total_candidates,
                total_refinements_generated=total_refinements,
            )

        # 5. Verify candidate patch in fresh execution handle
        verification = await verify_candidate_patch(
            candidate=candidate,
            recipe=recipe,
            sandbox=sandbox,
            host=host,
            baseline_collected_count=baseline_collected_count,
            baseline_preservation=baseline_preservation,
            checkpoint_id=checkpoint_id,
            mode=mode,
            artifact_prefix=f"{candidate_id}_",
            emit_stage_event=False,
        )

        attempt = BranchAttempt(
            attempt_id=candidate_id,
            branch_index=branch_idx,
            is_refinement=False,
            patch=candidate,
            validation=validation,
            verification=verification,
            duration_seconds=time.monotonic() - start_gen,
        )
        attempts.append(attempt)

        # 6. Early stopping on root candidate pass
        if verification.passed:
            await save_canonical_artifacts(host, candidate, verification)
            await host.emit(
                "stage.completed",
                {
                    "stage": "verification",
                    "passed": True,
                    "summary": f"Candidate {candidate_id} verified cleanly",
                },
            )
            return BranchSearchResult(
                state="succeeded",
                reason=f"Candidate {candidate_id} verified cleanly and resolved upgrade regression",
                winning_attempt=attempt,
                attempts=attempts,
                total_candidates_generated=total_candidates,
                total_refinements_generated=total_refinements,
            )

        # 7. Evaluate single refinement if allowed (0 disables refinement)
        if search_budget.max_refinements >= 1:
            if await host.cancelled():
                return BranchSearchResult(
                    state="cancelled",
                    reason=f"User cancelled before refinement of {candidate_id}",
                    attempts=attempts,
                    total_candidates_generated=total_candidates,
                    total_refinements_generated=total_refinements,
                )

            refine_id = f"{candidate_id}_refine_1"
            total_refinements += 1
            start_refine = time.monotonic()
            combined_output = f"{verification.stdout}\n{verification.stderr}".strip()
            failure_output = combined_output or verification.summary
            if not failure_output:
                failure_output = "Verification failed without output"

            try:
                refine_patch = await generate_refinement_patch(
                    recipe=recipe,
                    candidate=candidate,
                    failure_output=failure_output,
                    model=model,
                    host=host,
                    attempt_id=refine_id,
                    estimated_cost=search_budget.estimated_cost_per_generation,
                )
            except BudgetExceededError as exc:
                return BranchSearchResult(
                    state="failed",
                    reason=str(exc),
                    attempts=attempts,
                    total_candidates_generated=total_candidates,
                    total_refinements_generated=total_refinements,
                )
            except Exception as exc:
                # If refinement generation fails, record attempt and advance to next branch
                await host.emit(
                    "candidate.completed",
                    {
                        "candidate_id": refine_id,
                        "passed": False,
                        "summary": f"Refinement generation error: {exc}",
                    },
                )
                attempts.append(
                    BranchAttempt(
                        attempt_id=refine_id,
                        branch_index=branch_idx,
                        is_refinement=True,
                        parent_candidate_id=candidate_id,
                        duration_seconds=time.monotonic() - start_refine,
                    )
                )
                continue

            refine_validation = validate_patch(refine_patch.diff_content, recipe)
            if not refine_validation.valid:
                await host.emit(
                    "candidate.completed",
                    {
                        "candidate_id": refine_id,
                        "passed": False,
                        "summary": refine_validation.reason,
                    },
                )
                attempts.append(
                    BranchAttempt(
                        attempt_id=refine_id,
                        branch_index=branch_idx,
                        is_refinement=True,
                        parent_candidate_id=candidate_id,
                        patch=refine_patch,
                        validation=refine_validation,
                        duration_seconds=time.monotonic() - start_refine,
                    )
                )
                continue

            if await host.cancelled():
                return BranchSearchResult(
                    state="cancelled",
                    reason=f"User cancelled before verification of {refine_id}",
                    attempts=attempts,
                    total_candidates_generated=total_candidates,
                    total_refinements_generated=total_refinements,
                )

            refine_verification = await verify_candidate_patch(
                candidate=refine_patch,
                recipe=recipe,
                sandbox=sandbox,
                host=host,
                baseline_collected_count=baseline_collected_count,
                baseline_preservation=baseline_preservation,
                checkpoint_id=checkpoint_id,
                mode=mode,
                artifact_prefix=f"{refine_id}_",
                emit_stage_event=False,
            )

            refine_attempt = BranchAttempt(
                attempt_id=refine_id,
                branch_index=branch_idx,
                is_refinement=True,
                parent_candidate_id=candidate_id,
                patch=refine_patch,
                validation=refine_validation,
                verification=refine_verification,
                duration_seconds=time.monotonic() - start_refine,
            )
            attempts.append(refine_attempt)

            # Early stopping on refinement pass
            if refine_verification.passed:
                await save_canonical_artifacts(host, refine_patch, refine_verification)
                await host.emit(
                    "stage.completed",
                    {
                        "stage": "verification",
                        "passed": True,
                        "summary": f"Refined candidate {refine_id} verified cleanly",
                    },
                )
                return BranchSearchResult(
                    state="succeeded",
                    reason=f"Refined candidate {refine_id} verified cleanly and resolved upgrade regression",
                    winning_attempt=refine_attempt,
                    attempts=attempts,
                    total_candidates_generated=total_candidates,
                    total_refinements_generated=total_refinements,
                )

    # 8. All branches and refinements exhausted
    exhaustion_summary = (
        f"All {total_candidates} candidate branches and {total_refinements} refinements "
        f"failed verification"
    )
    await host.emit(
        "stage.completed",
        {
            "stage": "verification",
            "passed": False,
            "summary": exhaustion_summary,
        },
    )
    return BranchSearchResult(
        state="failed",
        reason=exhaustion_summary,
        attempts=attempts,
        total_candidates_generated=total_candidates,
        total_refinements_generated=total_refinements,
    )
