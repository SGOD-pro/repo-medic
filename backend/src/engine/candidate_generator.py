from src.contracts import HostPorts, TaskRecipe
from src.engine.adapters import ModelAdapter
from src.engine.candidate import CandidatePatch, UpgradeResult
from src.engine.extraction import extract_error_context
from src.engine.patch_validator import parse_modified_files


class BudgetExceededError(Exception):
    """Raised when host budget reservation is denied."""
    pass


def build_repair_prompt(
    recipe: TaskRecipe, upgrade: UpgradeResult, error_block: str, error_files: list[str]
) -> str:
    """Builds a bounded repair prompt for the language model."""
    files_hint = ", ".join(error_files) if error_files else "see error block"
    return (
        f"You are an expert automated Python repair engine for Repo Medic.\n"
        f"Task: {recipe.title}\n"
        f"Target dependency: {recipe.dependency} upgraded from {recipe.from_version} to {recipe.to_version}\n"
        f"Allowed source paths: {', '.join(recipe.allowed_source_paths)}\n"
        f"Error files detected: {files_hint}\n\n"
        f"--- Observed failure after upgrade ---\n"
        f"{error_block}\n\n"
        f"Generate a minimal unified diff patch to fix this failure.\n"
        f"Rules:\n"
        f"1. Only modify files within allowed source paths: {', '.join(recipe.allowed_source_paths)}.\n"
        f"2. Never edit test files, lockfiles, or project configuration files.\n"
        f"3. Return strictly a unified diff starting with '--- a/' and '+++ b/'.\n"
    )


def _strip_code_block(raw: str) -> str:
    """Cleans markdown code blocks wrapping diff content."""
    clean_diff = raw.strip()
    if clean_diff.startswith("```"):
        lines = clean_diff.splitlines()
        if len(lines) >= 2 and lines[0].startswith("```"):
            if lines[-1].startswith("```"):
                clean_diff = "\n".join(lines[1:-1]).strip()
            else:
                clean_diff = "\n".join(lines[1:]).strip()
    return clean_diff


async def generate_candidate_patch(
    recipe: TaskRecipe,
    upgrade: UpgradeResult,
    model: ModelAdapter,
    host: HostPorts,
    candidate_id: str = "candidate_1",
    estimated_cost: float = 0.0,
) -> CandidatePatch:
    """
    Generates a candidate patch from the model with budget reservation and prompt construction.
    """
    # 1. Reserve budget if operation has estimated cost
    op_id = f"candidate_gen_{candidate_id}"
    if estimated_cost > 0.0:
        reserved = await host.reserve(op_id, estimated_cost)
        if not reserved:
            raise BudgetExceededError(
                f"Budget reservation of ${estimated_cost:.4f} was denied by host"
            )

    try:
        # 2. Extract bounded error context from upgrade test output
        error_block, error_files = extract_error_context(upgrade.failure_output)

        # 3. Build prompt and invoke model completion with 2048 token cap
        prompt = build_repair_prompt(recipe, upgrade, error_block, error_files)
        raw_response = await model.complete(prompt, max_tokens=2048)

        clean_diff = _strip_code_block(raw_response)
        modified_files = parse_modified_files(clean_diff)

        if estimated_cost > 0.0:
            await host.settle(op_id, estimated_cost)

        return CandidatePatch(
            candidate_id=candidate_id,
            diff_content=clean_diff,
            modified_files=modified_files,
            raw_model_response=raw_response,
        )
    except Exception:
        if estimated_cost > 0.0:
            await host.settle(op_id, 0.0)
        raise


MAX_PROMPT_FAILURE_CHARS = 1500


def build_refinement_prompt(
    recipe: TaskRecipe,
    candidate: CandidatePatch,
    failure_output: str,
) -> str:
    """Builds a bounded refinement prompt incorporating prior candidate diff and failure output."""
    bounded_failure = failure_output.strip()
    if len(bounded_failure) > MAX_PROMPT_FAILURE_CHARS:
        bounded_failure = bounded_failure[:MAX_PROMPT_FAILURE_CHARS] + "\n... [truncated]"

    return (
        f"You are an expert automated Python repair engine for Repo Medic.\n"
        f"Task: {recipe.title}\n"
        f"Target dependency: {recipe.dependency} upgraded from {recipe.from_version} to {recipe.to_version}\n"
        f"Allowed source paths: {', '.join(recipe.allowed_source_paths)}\n\n"
        f"--- Previous Candidate Patch ({candidate.candidate_id}) ---\n"
        f"{candidate.diff_content}\n\n"
        f"--- Verification Failure Observed ---\n"
        f"{bounded_failure}\n\n"
        "Your previous candidate patch failed verification. Analyze the failure and provide "
        "an updated, complete unified diff patch that fixes the issue.\n"
        f"Rules:\n"
        f"1. Only modify files within allowed source paths: {', '.join(recipe.allowed_source_paths)}.\n"
        f"2. Never edit test files, lockfiles, or project configuration files.\n"
        f"3. Return strictly a unified diff starting with '--- a/' and '+++ b/'.\n"
    )


async def generate_refinement_patch(
    recipe: TaskRecipe,
    candidate: CandidatePatch,
    failure_output: str,
    model: ModelAdapter,
    host: HostPorts,
    attempt_id: str,
    estimated_cost: float = 0.0,
) -> CandidatePatch:
    """
    Generates a refined patch from the model with budget reservation and prior failure context.
    """
    op_id = f"candidate_refine_{attempt_id}"
    if estimated_cost > 0.0:
        reserved = await host.reserve(op_id, estimated_cost)
        if not reserved:
            raise BudgetExceededError(
                f"Budget reservation of ${estimated_cost:.4f} was denied by host"
            )

    try:
        prompt = build_refinement_prompt(recipe, candidate, failure_output)
        raw_response = await model.complete(prompt, max_tokens=2048)

        clean_diff = _strip_code_block(raw_response)
        modified_files = parse_modified_files(clean_diff)

        if estimated_cost > 0.0:
            await host.settle(op_id, estimated_cost)

        return CandidatePatch(
            candidate_id=attempt_id,
            diff_content=clean_diff,
            modified_files=modified_files,
            raw_model_response=raw_response,
        )
    except Exception:
        if estimated_cost > 0.0:
            await host.settle(op_id, 0.0)
        raise
