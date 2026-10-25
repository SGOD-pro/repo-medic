#!/usr/bin/env python3
"""Live sequential repair runner for RepoMedic milestone K4.

Validates end to end live integration with Nebius Token Factory inference
and ConTree container sandboxes against a verified repository recipe.
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

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
from src.contracts import TaskRecipe  # noqa: E402
from src.preflight import verify_live_providers  # noqa: E402
from src.storage.db_client import RepoMedicDB  # noqa: E402
from src.storage.repository import D1StorageRepository  # noqa: E402
from src.worker import QueueWorker  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


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
        title="sqlalchemy v1.4.48 to v2.0.19 in repo-medic fixture",
        repository_url="https://github.com/SGOD-pro/repo-medic.git",
        commit_sha="453a0b6c6b125177504cdd941902b8d48266ed1c",
        dependency="sqlalchemy",
        from_version="1.4.48",
        to_version="2.0.19",
        test_command=["pytest", "tests/"],
        allowed_source_paths=["src/backend/database.py", "src/backend/models.py"],
        expected_failure="AttributeError: 'Engine' object has no attribute 'execute'",
        timeout_seconds=600,
        max_candidates=3,
        max_refinements=1,
    )


DEFAULT_PINNED_RECIPE = _load_default_recipe()


def sanitize_text(text: str, secrets: List[str]) -> str:
    """Replace sensitive secret strings with redaction markers."""
    result = text
    for secret in secrets:
        cleaned = secret.strip()
        if len(cleaned) >= 6:
            result = result.replace(cleaned, "***REDACTED***")
    return result


def get_d1_repository() -> D1StorageRepository:
    """Connect to configured D1 bridge, falling back to local SQLite transport."""
    client = RepoMedicDB()
    try:
        client.health()
        return D1StorageRepository(client)
    except Exception:
        from tests.test_storage import create_sqlite_d1_transport
        token = getattr(settings, "repomedic_db_worker_token", "dev-token")
        transport = create_sqlite_d1_transport(expected_token=token)
        db = RepoMedicDB(
            base_url="http://local-d1-bridge",
            api_key=token,
            transport=transport,
        )
        return D1StorageRepository(db)


async def run_live(
    recipe: TaskRecipe,
    dry_run: bool = False,
    run_id_override: str | None = None,
    search_mode_override: str | None = None,
) -> int:
    token_factory_key = (
        os.environ.get("TOKEN_FACTORY_API_KEY")
        or settings.token_factory_api_key
        or os.environ.get("NEBIUS_API_KEY")
        or settings.nebius_api_key
        or ""
    ).strip()
    nebius_key = (os.environ.get("NEBIUS_API_KEY") or settings.nebius_api_key or "").strip()
    project_id = (
        os.environ.get("NEBIUS_PROJECT_ID")
        or settings.nebius_project_id
        or settings.token_factory_sandbox_project_id
        or ""
    ).strip()

    search_mode = search_mode_override
    if search_mode is None:
        manifest_path = repo_root / "fixtures" / "evaluation_manifest.json"
        if manifest_path.is_file():
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest_data = json.load(f)
                for sc in manifest_data.get("scenarios", []):
                    if sc.get("task_id") == recipe.task_id:
                        search_mode = sc.get("search_mode")
                        break
            except Exception:
                pass
    if search_mode not in ("sequential", "branch_refine"):
        search_mode = "sequential"

    print("=== RepoMedic Live Repair Runner ===")
    print(f"Task: {recipe.task_id} ({recipe.title})")
    print(f"Repository: {recipe.repository_url} @ {recipe.commit_sha}")
    print(f"Search mode: {search_mode}")
    print(f"Upgrade target: {recipe.dependency} {recipe.from_version} to {recipe.to_version}")
    print(f"Base sandbox image: {settings.nebius_sandbox_image}")
    print(f"Inference model: {settings.token_factory_model}")
    print(f"Run spending ceiling: ${settings.repomedic_max_run_usd:.2f} USD")
    print(f"Global spending ceiling: ${settings.repomedic_total_budget_usd:.2f} USD")

    # 1. Preflight validation before paid execution
    print("\nRunning preflight validation checks...")
    preflight = verify_live_providers(
        repository_url=recipe.repository_url,
        commit_sha=recipe.commit_sha,
        timeout_seconds=recipe.timeout_seconds,
    )

    for check in preflight.checks:
        status_label = "PASS" if check.get("passed") else "FAIL"
        print(f"[{status_label}] {check.get('name')}")

    if not preflight.passed:
        print("\nPreflight validation failed with the following issues:")
        for err in preflight.errors:
            print(f"  * {err}")

        if dry_run:
            print("\nDry run mode active: skipping cloud execution due to preflight failures.")
            return 0
        return 1

    if dry_run:
        print("\nDry run mode active: all preflight verifications passed cleanly. Skipping cloud execution.")
        return 0

    # 2. Execution through production API, QueueWorker, and D1HostPorts path
    repo = get_d1_repository()
    recipe_dict = {
        "test_command": recipe.test_command,
        "allowed_source_paths": recipe.allowed_source_paths,
        "expected_failure": recipe.expected_failure,
        "timeout_seconds": recipe.timeout_seconds,
        "max_candidates": recipe.max_candidates,
        "max_refinements": recipe.max_refinements,
    }
    repo.upsert_task({
        "task_id": recipe.task_id,
        "title": recipe.title,
        "repository_url": recipe.repository_url,
        "commit_sha": recipe.commit_sha,
        "dependency": recipe.dependency,
        "from_version": recipe.from_version,
        "to_version": recipe.to_version,
        "recipe_json": json.dumps(recipe_dict),
    })

    run_id = run_id_override or f"run_k4_live_{int(time.time())}"

    print(f"\nSubmitting live run {run_id} to database queue...")
    repo.create_run(
        run_id=run_id,
        task_id=recipe.task_id,
        mode="live",
        search_mode=search_mode,
        max_run_usd=settings.repomedic_max_run_usd,
    )

    worker = QueueWorker(repo=repo, acceptance_prefix=run_id)
    print("Processing run via QueueWorker and D1HostPorts...")

    try:
        processed = await worker.process_one()
        if not processed:
            print(f"Error: QueueWorker failed to claim run {run_id}.")
            return 1
    except Exception as exc:
        print(f"Fatal execution error during run: {exc}")
        return 1

    run_record = repo.get_run(run_id)
    run_state = run_record.state
    run_reason = run_record.reason or ""

    print(f"\nRun {run_id} completed with state: {run_state.upper()}")
    if run_reason:
        print(f"Termination note: {run_reason}")

    # 3. Retrieve and persist durable artifacts
    artifacts_dir = repo_root / "artifacts" / run_id
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    saved_artifacts: Dict[str, Path] = {}

    for art in run_record.artifacts:
        content_bytes = repo.get_artifact_content(run_id, art.artifact_id)
        file_path = artifacts_dir / art.filename
        file_path.write_bytes(content_bytes)
        saved_artifacts[art.filename] = file_path
        print(f"Saved artifact {art.filename} ({len(content_bytes)} bytes) to {file_path}")

    # 4. Display budget reservations clearly labeled as estimated allocations
    print("\nBudget settlements (Estimated allocations, not measured cloud billing):")
    usage = run_record.usage
    in_tokens_str = (
        str(usage.input_tokens)
        if usage.input_tokens > 0
        else "unavailable (provider omitted token usage)"
    )
    out_tokens_str = (
        str(usage.output_tokens)
        if usage.output_tokens > 0
        else "unavailable (provider omitted token usage)"
    )
    print(f"  * Model calls: {usage.model_calls}")
    print(f"  * Input tokens: {in_tokens_str}, Output tokens: {out_tokens_str}")
    print(f"  * Run estimated allocation: ${usage.estimated_usd:.4f} USD")

    budget_usage = repo.client.get_budget_usage()
    settled_micro = budget_usage.get("settled_micro_usd", 0)
    total_settled_usd = settled_micro / 1_000_000.0
    print(f"Global estimated allocation settled: ${total_settled_usd:.4f} USD")

    # 5. Handle success or failure outcomes
    known_secrets = [token_factory_key, nebius_key, project_id]

    if run_state == "succeeded":
        print("\nSequential repair run succeeded!")
        print(f"Evidence manifest: {saved_artifacts.get('evidence.json')}")
        print(f"Verified patch diff: {saved_artifacts.get('patch.diff')}")
        print(f"Verification log: {saved_artifacts.get('verify.log')}")
        return 0

    print(f"\nSequential repair run failed in state '{run_state}'.")
    failure_data: Dict[str, Any] = {
        "run_id": run_id,
        "task_id": recipe.task_id,
        "state": run_state,
        "reason": sanitize_text(run_reason, known_secrets),
        "total_estimated_usd": total_settled_usd,
        "timestamp": int(time.time()),
    }

    try:
        events = repo.list_events(run_id)
        failure_data["events"] = [
            {"seq": e.seq, "type": e.type, "payload": e.payload}
            for e in events
        ]
    except Exception:
        pass

    if "verify.log" in saved_artifacts:
        raw_log = saved_artifacts["verify.log"].read_text(encoding="utf-8", errors="replace")
        failure_data["sanitized_log"] = sanitize_text(raw_log, known_secrets)

    failure_file = repo_root / "artifacts" / f"live_repair_failure_{int(time.time())}.json"
    failure_file.parent.mkdir(parents=True, exist_ok=True)
    raw_failure_json = json.dumps(failure_data, indent=2)
    sanitized_failure_json = sanitize_text(raw_failure_json, known_secrets)
    with open(failure_file, "w", encoding="utf-8") as fp:
        fp.write(sanitized_failure_json)

    print(f"Sanitized failure details recorded to: {failure_file}")
    print("Add an offline regression reproducing this issue before initiating another paid attempt.")
    return 1


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
    parser.add_argument(
        "--run-id",
        type=str,
        default=None,
        help="Optional run identifier override",
    )
    parser.add_argument(
        "--search-mode",
        choices=["sequential", "branch_refine"],
        default=None,
        help="Optional search mode override (sequential or branch_refine)",
    )
    args = parser.parse_args()

    recipe = DEFAULT_PINNED_RECIPE
    if args.recipe and args.recipe.is_file():
        with open(args.recipe, "r", encoding="utf-8") as f:
            data = json.load(f)
        recipe = TaskRecipe.model_validate(data)

    return asyncio.run(
        run_live(
            recipe,
            dry_run=args.dry_run,
            run_id_override=args.run_id,
            search_mode_override=args.search_mode,
        )
    )


if __name__ == "__main__":
    sys.exit(main())
