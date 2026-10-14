from pathlib import Path
from src.contracts import TaskRecipe


class RecipeValidationError(ValueError):
    """Raised when a TaskRecipe fails validation rules."""
    pass


def validate_recipe(recipe: TaskRecipe) -> None:
    """
    Validates task recipe according to engine safety invariants.
    Ensures safe execution bounds and path traversal protections.
    """
    if not recipe.task_id or not recipe.task_id.strip():
        raise RecipeValidationError("task_id must be a non-empty string")

    if not recipe.test_command:
        raise RecipeValidationError("test_command must not be empty")

    if not all(isinstance(c, str) and c.strip() for c in recipe.test_command):
        raise RecipeValidationError("test_command must contain non-empty string arguments")

    if recipe.timeout_seconds <= 0:
        raise RecipeValidationError("timeout_seconds must be positive")

    if not recipe.allowed_source_paths:
        raise RecipeValidationError("allowed_source_paths must not be empty")

    for raw_path in recipe.allowed_source_paths:
        if not raw_path or not raw_path.strip():
            raise RecipeValidationError("allowed_source_paths contains an empty path")

        normalized = raw_path.replace("\\", "/")
        path = Path(normalized)
        if path.is_absolute() or raw_path.startswith("/") or raw_path.startswith("\\"):
            raise RecipeValidationError(
                f"allowed_source_paths must be relative, got absolute path: '{raw_path}'"
            )

        if ".." in path.parts:
            raise RecipeValidationError(
                f"allowed_source_paths cannot traverse parent directories: '{raw_path}'"
            )

    if not recipe.repository_url or not recipe.repository_url.strip():
        raise RecipeValidationError("repository_url must be a non-empty string")

    if not recipe.commit_sha or not recipe.commit_sha.strip():
        raise RecipeValidationError("commit_sha must be a non-empty string")

    if not recipe.expected_failure or not recipe.expected_failure.strip():
        raise RecipeValidationError("expected_failure must be a non-empty string")
