#!/usr/bin/env python3
"""Live sequential repair runner for RepoMedic milestone K4.

Validates end to end live integration with Nebius Token Factory inference
and ConTree container sandboxes against a pinned repository recipe.
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
    _backend_env = Path(__file__).resolve().parents[1] / "backend" / ".env"
    if _backend_env.is_file():
        load_dotenv(_backend_env)
except ImportError:
    pass

repo_root = Path(__file__).resolve().parents[1]
backend_dir = repo_root / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from src.config import settings  # noqa: E402
from src.contracts import RepairRequest, TaskRecipe  # noqa: E402
from src.engine.contree_sandbox import ConTreeSandboxAdapter  # noqa: E402
from src.engine.repair import repair as engine_repair  # noqa: E402
from src.engine.token_factory_model import TokenFactoryModelAdapter  # noqa: E402
from src.storage.fake_host import FakeHost  # noqa: E402


def _load_default_recipe() -> TaskRecipe:
    fixture_path = repo_root / "fixtures" / "tasks" / "TASK-091.json"
    if fixture_path.is_file():
        try:
            with open(fixture_path, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            return TaskRecipe.model_validate(data)
        except Exception:
            pass
    return TaskRecipe(
        task_id="TASK-091",
        title="sqlalchemy v1.4.48 -> v2.0.19 in backend-core",
        repository_url="https://github.com/pallets/backend-core",
        commit_sha="c39b104",
        dependency="sqlalchemy",
        from_version="1.4.48",
        to_version="2.0.19",
        test_command=["pytest", "tests/"],
        allowed_source_paths=["src/backend/database.py", "src/backend/models.py"],
        expected_failure="RemovedIn20Warning escalated to error: engine.execute() removed in 2.0",
        timeout_seconds=600,
        max_candidates=3,
        max_refinements=1,
    )


DEFAULT_PINNED_RECIPE = _load_default_recipe()


async def run_live(recipe: TaskRecipe, dry_run: bool = False) -> int:
    token_factory_key = (
        os.environ.get("TOKEN_FACTORY_API_KEY")
        or settings.token_factory_api_key
        or os.environ.get("NEBIUS_API_KEY")
        or settings.nebius_api_key
    ).strip()
    nebius_key = (os.environ.get("NEBIUS_API_KEY") or settings.nebius_api_key).strip()
    project_id = (
        os.environ.get("NEBIUS_PROJECT_ID")
        or settings.nebius_project_id
        or settings.token_factory_sandbox_project_id
    ).strip()

    print("=== RepoMedic K4 Live Sequential Repair ===")
    print(f"Task: {recipe.task_id} ({recipe.title})")
    print(f"Repository: {recipe.repository_url} @ {recipe.commit_sha}")
    print(f"Upgrade: {recipe.dependency} {recipe.from_version} -> {recipe.to_version}")
    print(f"Base sandbox image: {settings.nebius_sandbox_image}")
    print(f"Inference model: {settings.token_factory_model}")

    if not token_factory_key or not nebius_key or not project_id:
        print("\nOperator credentials missing:")
        if not token_factory_key:
            print("  * TOKEN_FACTORY_API_KEY is not set")
        if not nebius_key:
            print("  * NEBIUS_API_KEY is not set")
        if not project_id:
            print("  * NEBIUS_PROJECT_ID is not set")

        if dry_run:
            print("\nDry run mode active: skipping live cloud execution.")
            return 0

        print("\nTo execute against live Nebius endpoints, set the above variables and rerun.")
        return 1

    if dry_run:
        print("\nDry run mode active: credentials validated, skipping live cloud execution.")
        return 0

    request = RepairRequest(
        run_id="k4_live_sequential_run",
        task_id=recipe.task_id,
        mode="live",
        search_mode="sequential",
        max_run_usd=2.0,
    )

    host = FakeHost()
    sandbox = ConTreeSandboxAdapter(
        api_key=nebius_key,
        project_id=project_id,
        base_image=settings.nebius_sandbox_image,
        timeout_seconds=600,
    )
    model = TokenFactoryModelAdapter(
        api_key=token_factory_key,
        base_url=settings.token_factory_base_url,
        model=settings.token_factory_model,
    )

    try:
        print("\nExecuting sequential repair in live mode...")
        result = await engine_repair(
            request=request,
            recipe=recipe,
            host=host,
            sandbox=sandbox,
            model=model,
        )
        print(f"\nExecution finished with state: {result.state.upper()}")
        print(f"Reason: {result.reason}")

        print("\nSettled budget reservations:")
        for op_id, amount in host.settlements.items():
            print(f"  * {op_id}: ${amount:.4f}")

        return 0 if result.state == "succeeded" else 1
    finally:
        print("\nCleaning up sandbox resources...")
        await sandbox.cleanup()
        print("Teardown complete.")


def main() -> int:
    parser = argparse.ArgumentParser(description="K4 live sequential repair runner")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate configuration without making paid cloud provider calls",
    )
    parser.add_argument(
        "--recipe",
        type=Path,
        default=None,
        help="Optional path to custom task recipe JSON file",
    )
    args = parser.parse_args()

    recipe = DEFAULT_PINNED_RECIPE
    if args.recipe and args.recipe.is_file():
        with open(args.recipe, "r", encoding="utf-8") as f:
            data = json.load(f)
        recipe = TaskRecipe.model_validate(data)

    return asyncio.run(run_live(recipe, dry_run=args.dry_run))


if __name__ == "__main__":
    sys.exit(main())
