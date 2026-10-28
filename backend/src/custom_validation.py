import re
from typing import Dict, List
from src.contracts import CustomRepositoryConfig, CustomConfigValidationResponse

GITHUB_HTTPS_REGEX = re.compile(
    r"^https://github\.com/[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+(?:\.git)?/?$"
)
HEX_40_REGEX = re.compile(r"^[0-9a-fA-F]{40}$")
PYTHON_PACKAGE_REGEX = re.compile(r"^[a-zA-Z0-9_.-]+$")
DANGEROUS_COMMAND_REGEX = re.compile(
    r"(?:^|[;&|\s])(?:sh|bash|zsh|curl|wget|rm|sudo|chmod|eval|exec|python\s+-c)(?:$|[;&|\s])|[;&|><`$]"
)


def validate_custom_config(config: CustomRepositoryConfig) -> CustomConfigValidationResponse:
    errors: List[str] = []
    field_errors: Dict[str, List[str]] = {}

    def add_error(field: str, msg: str) -> None:
        errors.append(msg)
        if field not in field_errors:
            field_errors[field] = []
        field_errors[field].append(msg)

    # Repository URL validation
    repo_url = (config.repository_url or "").strip()
    if not repo_url:
        add_error("repository_url", "Repository URL is required")
    elif not GITHUB_HTTPS_REGEX.match(repo_url):
        add_error(
            "repository_url",
            "Repository URL must be a public GitHub HTTPS URL (e.g. https://github.com/owner/repo)",
        )

    # Commit SHA validation
    commit_sha = (config.commit_sha or "").strip()
    if not commit_sha:
        add_error("commit_sha", "Commit SHA is required")
    elif not HEX_40_REGEX.match(commit_sha):
        add_error(
            "commit_sha",
            "Commit SHA must be a full 40 character hexadecimal string",
        )

    # Dependency name validation
    dependency = (config.dependency or "").strip()
    if not dependency:
        add_error("dependency", "Dependency name is required")
    elif not PYTHON_PACKAGE_REGEX.match(dependency):
        add_error(
            "dependency",
            "Dependency name must be a valid Python package name",
        )

    # Baseline version validation
    from_version = (config.from_version or "").strip()
    if not from_version:
        add_error("from_version", "Baseline version is required")

    # Target version validation
    to_version = (config.to_version or "").strip()
    if not to_version:
        add_error("to_version", "Target version is required")
    elif from_version and to_version == from_version:
        add_error(
            "to_version",
            "Target version must differ from baseline version",
        )

    # Pytest args validation
    if not config.pytest_args or not isinstance(config.pytest_args, list):
        add_error("pytest_args", "Pytest arguments list cannot be empty")
    else:
        has_non_empty = False
        has_unsafe = False
        for arg in config.pytest_args:
            if not isinstance(arg, str):
                has_unsafe = True
                continue
            trimmed = arg.strip()
            if trimmed:
                has_non_empty = True
                if DANGEROUS_COMMAND_REGEX.search(trimmed):
                    has_unsafe = True
        if not has_non_empty:
            add_error("pytest_args", "Pytest arguments list cannot be empty")
        elif has_unsafe:
            add_error(
                "pytest_args",
                "Pytest arguments must not contain shell operators or command escapes",
            )

    # Allowed relative source paths validation
    if not config.allowed_source_paths or not isinstance(config.allowed_source_paths, list):
        add_error("allowed_source_paths", "Allowed source paths list cannot be empty")
    else:
        has_non_empty_path = False
        has_path_traversal = False
        for path in config.allowed_source_paths:
            if not isinstance(path, str):
                has_path_traversal = True
                continue
            trimmed = path.strip()
            if trimmed:
                has_non_empty_path = True
                if trimmed.startswith("/") or trimmed.startswith("\\") or ":" in trimmed:
                    has_path_traversal = True
                parts = trimmed.replace("\\", "/").split("/")
                if ".." in parts or "." in parts:
                    has_path_traversal = True
        if not has_non_empty_path:
            add_error("allowed_source_paths", "Allowed source paths list cannot be empty")
        elif has_path_traversal:
            add_error(
                "allowed_source_paths",
                "Allowed source paths must be relative paths within repository root and cannot contain parent directory traversal (..)",
            )

    # Expected failure substring validation
    expected_failure = (config.expected_failure or "").strip()
    if not expected_failure:
        add_error("expected_failure", "Expected failure substring is required")

    return CustomConfigValidationResponse(
        valid=len(errors) == 0,
        errors=errors,
        field_errors=field_errors,
        custom_execution_supported=False,
        gate_status="disabled",
        gate_message=(
            "Custom repository execution is disabled in this safe product slice. "
            "Arbitrary remote execution, background worker enqueueing, provider calls, "
            "and task execution are strictly gated off."
        ),
    )
