import re
from pathlib import PurePosixPath
from typing import List, Set
from src.contracts import TaskRecipe
from src.engine.candidate import PatchValidationResult

DIFF_HEADER_PATTERN = re.compile(
    r"^(?:---|\+\+\+)\s+(?:[ab]/)?([^\s\t\n]+)", re.MULTILINE
)
GIT_DIFF_HEADER = re.compile(
    r"^diff --git\s+(?:[ab]/)?([^\s]+)\s+(?:[ab]/)?([^\s]+)", re.MULTILINE
)

# Prohibited paths and filenames that candidate patches must never modify
PROHIBITED_PREFIXES = ("tests/", "test/", ".git/", ".github/", ".agents/")
PROHIBITED_FILES = {
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "requirements.txt",
    "requirements-dev.txt",
    "tox.ini",
    "uv.lock",
    "poetry.lock",
    "Pipfile.lock",
    ".gitignore",
}


def parse_modified_files(diff_content: str) -> List[str]:
    """Extracts unique relative target paths modified by a unified diff."""
    modified_paths: Set[str] = set()

    for match in GIT_DIFF_HEADER.finditer(diff_content):
        p1, p2 = match.group(1), match.group(2)
        if p2 and p2 != "/dev/null":
            modified_paths.add(_normalize_path(p2))
        elif p1 and p1 != "/dev/null":
            modified_paths.add(_normalize_path(p1))

    for match in DIFF_HEADER_PATTERN.finditer(diff_content):
        path_str = match.group(1)
        if path_str and path_str != "/dev/null":
            modified_paths.add(_normalize_path(path_str))

    return sorted(list(modified_paths))


def _normalize_path(path_str: str) -> str:
    path_str = path_str.strip().replace("\\", "/")
    if path_str.startswith("a/") or path_str.startswith("b/"):
        path_str = path_str[2:]
    return path_str.lstrip("/")


def _is_path_allowed(path_str: str, allowed_paths: List[str]) -> bool:
    """Checks whether a path falls strictly under at least one allowed directory or file."""
    for allowed in allowed_paths:
        norm_allowed = _normalize_path(allowed)
        if norm_allowed.endswith("/"):
            if path_str.startswith(norm_allowed):
                return True
        else:
            if path_str == norm_allowed or path_str.startswith(f"{norm_allowed}/"):
                return True
    return False


# Public aliases for engine modules
normalize_path = _normalize_path
is_path_allowed = _is_path_allowed


def validate_patch(diff_content: str, recipe: TaskRecipe) -> PatchValidationResult:
    """
    Validates that a candidate patch is safe to apply:
    1. Must contain valid diff syntax and modify at least one file.
    2. Modified files must not escape workspace root (no '..', no absolute paths).
    3. Modified files must be within recipe.allowed_source_paths.
    4. Must not edit tests, configuration files, manifests, or lockfiles.
    """
    if not diff_content or not diff_content.strip():
        return PatchValidationResult(
            valid=False,
            reason="Candidate patch is empty",
            violations=["Empty diff content"],
        )

    modified_files = parse_modified_files(diff_content)
    if not modified_files:
        return PatchValidationResult(
            valid=False,
            reason="No modified file targets found in patch header",
            violations=["No file headers matched in diff"],
        )

    if not re.search(r"^@@\s+-\d+", diff_content, re.MULTILINE):
        return PatchValidationResult(
            valid=False,
            reason="Candidate patch contains no valid diff hunks (incomplete or truncated diff)",
            violations=["No diff hunks found in patch"],
        )

    violations: List[str] = []

    for file_path in modified_files:
        # Check path traversal
        posix = PurePosixPath(file_path)
        if ".." in posix.parts or posix.is_absolute():
            violations.append(f"Path traversal detected: {file_path}")
            continue

        # Check prohibited files and prefixes
        filename = posix.name
        if filename in PROHIBITED_FILES or filename.startswith("test_") or filename.endswith("_test.py"):
            violations.append(
                f"Modifications to configuration, lockfile, or test file not permitted: {file_path}"
            )
            continue

        if any(file_path.startswith(prefix) for prefix in PROHIBITED_PREFIXES):
            violations.append(
                f"Modifications to test or metadata directories not permitted: {file_path}"
            )
            continue

        # Check allowed source paths allowlist
        if not _is_path_allowed(file_path, recipe.allowed_source_paths):
            violations.append(
                f"File '{file_path}' is outside recipe allowed source paths {recipe.allowed_source_paths}"
            )

    if violations:
        return PatchValidationResult(
            valid=False,
            reason=f"Patch safety validation failed: {'; '.join(violations)}",
            violations=violations,
        )

    return PatchValidationResult(valid=True, reason="Patch passed safety checks")
