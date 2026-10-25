import difflib
import logging
import re
from typing import Dict, List, Optional

from src.contracts import HostPorts, TaskRecipe
from src.engine.adapters import ModelAdapter
from src.engine.candidate import CandidatePatch, UpgradeResult
from src.engine.extraction import extract_error_context
from src.engine.patch_validator import parse_modified_files

logger = logging.getLogger("repomedic.candidate_generator")


class BudgetExceededError(Exception):
    """Raised when host budget reservation is denied."""
    pass


def build_repair_prompt(
    recipe: TaskRecipe,
    upgrade: UpgradeResult,
    error_block: str,
    error_files: List[str],
    source_files: Optional[Dict[str, str]] = None,
) -> str:
    """Builds a bounded repair prompt for the language model."""
    files_hint = ", ".join(error_files) if error_files else "see error block"
    source_section = ""
    if source_files:
        rendered_files = []
        for path, content in source_files.items():
            rendered_files.append(f"File: {path}\n```python\n{content}\n```")
        source_section = "\n--- Current source file content ---\n" + "\n\n".join(rendered_files) + "\n"

    return (
        f"You are an expert automated Python repair engine for Repo Medic.\n"
        f"Task: {recipe.title}\n"
        f"Target dependency: {recipe.dependency} upgraded from {recipe.from_version} to {recipe.to_version}\n"
        f"Allowed source paths: {', '.join(recipe.allowed_source_paths)}\n"
        f"Error files detected: {files_hint}\n"
        f"{source_section}\n"
        f"--- Observed failure after upgrade ---\n"
        f"{error_block}\n\n"
        f"Generate a minimal unified diff patch to fix this failure.\n"
        f"Rules:\n"
        f"1. Only modify files within allowed source paths: {', '.join(recipe.allowed_source_paths)}.\n"
        f"2. Never edit test files, lockfiles, or project configuration files.\n"
        f"3. Return strictly a unified diff starting with '--- a/' and '+++ b/'.\n"
        f"4. Do NOT output conversational explanations, preamble, or markdown outside the diff.\n"
        f"5. Output valid unified diff hunks with standard '@@ -start,count +start,count @@' headers and "
        f"context lines from the source file. Do not output bare '@@' delimiters.\n"
        f"6. For SQLAlchemy 2.0 upgrades:\n"
        f"   - Replace legacy 'engine.execute(...)' calls with 'with engine.begin() as conn:' and "
        f"'conn.execute(...)'.\n"
        f"   - If 'Row has no attribute _default_key_style' occurs, in SQLAlchemy 2.0 Row(metadata, processors, "
        f"keymap, row) no longer accepts _default_key_style. Remove _default_key_style from Row(...) calls.\n"
        f"7. Start immediately with the diff header. Do not write any conversational introduction or summary.\n"
    )


def normalize_diff_context(diff_text: str, source_files: Optional[Dict[str, str]] = None) -> str:
    """Normalize patch hunks by restoring missing blank line context and repairing bare hunk headers."""
    lines = diff_text.splitlines()
    repaired_lines: List[str] = []
    current_file: Optional[str] = None
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("--- a/"):
            rel_path = line[6:].strip()
            current_file = rel_path if source_files and rel_path in source_files else None
            repaired_lines.append(line)
            i += 1
            continue
        if line.startswith("+++ b/"):
            repaired_lines.append(line)
            i += 1
            continue

        if line.startswith("@@"):
            hunk_lines: List[str] = []
            j = i + 1
            while j < len(lines) and not lines[j].startswith(("--- ", "+++ ", "diff ", "@@")):
                hunk_lines.append(lines[j])
                j += 1

            old_count = sum(1 for h_line in hunk_lines if not h_line.startswith("+"))
            new_count = sum(1 for h_line in hunk_lines if not h_line.startswith("-"))

            if old_count == 0 and new_count == 0:
                i = j
                continue

            if not re.match(r"^@@\s+-\d+", line):
                start_line = 1
                if current_file and source_files:
                    src_lines = source_files[current_file].splitlines()
                    first_ctx = None
                    for h_line in hunk_lines:
                        if h_line.startswith((" ", "-")) and h_line[1:].strip():
                            first_ctx = h_line[1:]
                            break
                    if first_ctx is not None:
                        for idx, s_line in enumerate(src_lines):
                            if s_line == first_ctx:
                                start_line = idx + 1
                                break

                repaired_lines.append(f"@@ -{start_line},{old_count} +{start_line},{new_count} @@")
                i += 1
                continue
        repaired_lines.append(line)
        i += 1

    if not source_files:
        return "\n".join(repaired_lines) + ("\n" if diff_text.endswith("\n") else "")

    current_file = None
    new_lines: List[str] = []
    for i, line in enumerate(repaired_lines):
        if line.startswith("--- a/"):
            rel_path = line[6:].strip()
            current_file = rel_path if rel_path in source_files else None
        elif line.startswith("+++ b/"):
            pass
        elif (
            current_file
            and i > 0
            and line.startswith(" ")
            and line.strip().startswith(("def ", "class ", "async def "))
        ):
            prev = repaired_lines[i - 1]
            if prev.startswith(("+", "-")):
                src_content = source_files[current_file]
                src_lines = src_content.splitlines()
                target_str = line.strip()
                for s_idx, s_line in enumerate(src_lines):
                    if s_line.strip() == target_str:
                        if s_idx > 0 and src_lines[s_idx - 1].strip() == "":
                            new_lines.append(" ")
                        break
        new_lines.append(line)

    return "\n".join(new_lines) + "\n"


def _strip_code_block(raw: str, source_files: Optional[Dict[str, str]] = None) -> str:
    """Cleans markdown code blocks or conversational text wrapping diff content."""
    text = raw.strip()

    # 1. Look for fenced diff or patch blocks
    fenced_match = re.search(r"```(?:diff|patch)?\s*\n([\s\S]*?)```", text)
    if fenced_match:
        inner = fenced_match.group(1).strip()
        if "--- a/" in inner or "diff --git" in inner:
            text = inner

    # 2. Find start of unified diff header
    diff_start = re.search(r"(?:^|\n)(diff --git\s+|---(?:\s+[ab]/|\s+\S))", text)
    if diff_start:
        start_idx = diff_start.start(1)
        text = text[start_idx:]

        # 3. Strip trailing conversational commentary after diff hunks
        lines = text.splitlines()
        diff_lines: List[str] = []
        in_hunk = False
        for line in lines:
            if line.startswith(("diff --git ", "--- ", "+++ ", "index ")):
                diff_lines.append(line)
            elif line.startswith("@@"):
                in_hunk = True
                diff_lines.append(line)
            elif in_hunk:
                if line.startswith(("+", "-", " ", "\\")) or line == "":
                    diff_lines.append(line)
                else:
                    break
            else:
                diff_lines.append(line)

        result = "\n".join(diff_lines).strip()
        clean = (result + "\n") if result else (raw.strip() + "\n")
        return normalize_diff_context(clean, source_files)

    # 4. Fallback: if model produced updated python code in fenced block instead of diff, compute unified diff
    if source_files:
        py_match = re.search(r"```(?:python)\s*\n([\s\S]*?)```", text)
        code_body = py_match.group(1).strip() if py_match else ""
        if code_body and code_body.startswith(("import ", "from ", "#!", "class ", "def ")):
            for file_path, orig_content in source_files.items():
                orig_lines = orig_content.splitlines(keepends=True)
                new_lines = [line_str + "\n" for line_str in code_body.splitlines()]
                diff_lines = list(
                    difflib.unified_diff(
                        orig_lines,
                        new_lines,
                        fromfile=f"a/{file_path}",
                        tofile=f"b/{file_path}",
                    )
                )
                if diff_lines:
                    return "".join(diff_lines)

    return raw.strip() + "\n"


async def generate_candidate_patch(
    recipe: TaskRecipe,
    upgrade: UpgradeResult,
    model: ModelAdapter,
    host: HostPorts,
    candidate_id: str = "candidate_1",
    estimated_cost: float = 0.0,
    source_files: Optional[Dict[str, str]] = None,
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
        prompt = build_repair_prompt(
            recipe, upgrade, error_block, error_files, source_files=source_files
        )
        raw_response = await model.complete(prompt, max_tokens=2048)
        logger.info("Raw model completion (%d chars): %s", len(raw_response), repr(raw_response[:200]))

        clean_diff = _strip_code_block(raw_response, source_files=source_files)
        modified_files = parse_modified_files(clean_diff)

        if estimated_cost > 0.0:
            await host.settle(op_id, estimated_cost)

        model_calls = getattr(model, "call_count", 1)
        in_tokens = getattr(model, "total_prompt_tokens", 0)
        out_tokens = getattr(model, "total_completion_tokens", 0)
        try:
            await host.emit(
                "usage.updated",
                {
                    "model_calls": max(1, model_calls),
                    "input_tokens": in_tokens,
                    "output_tokens": out_tokens,
                    "estimated_usd": estimated_cost,
                },
            )
        except Exception as exc:
            logger.warning("Could not emit usage.updated event: %s", exc)

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
    source_files: Optional[Dict[str, str]] = None,
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
        logger.info("Raw model completion (%d chars): %s", len(raw_response), repr(raw_response[:200]))

        clean_diff = _strip_code_block(raw_response, source_files=source_files)
        modified_files = parse_modified_files(clean_diff)

        if estimated_cost > 0.0:
            await host.settle(op_id, estimated_cost)

        model_calls = getattr(model, "call_count", 1)
        in_tokens = getattr(model, "total_prompt_tokens", 0)
        out_tokens = getattr(model, "total_completion_tokens", 0)
        try:
            await host.emit(
                "usage.updated",
                {
                    "model_calls": max(1, model_calls),
                    "input_tokens": in_tokens,
                    "output_tokens": out_tokens,
                    "estimated_usd": estimated_cost,
                },
            )
        except Exception as exc:
            logger.warning("Could not emit usage.updated event: %s", exc)

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
