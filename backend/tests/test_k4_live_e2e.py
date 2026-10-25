import json
import os
import pytest

from src.config import settings
from src.contracts import TaskRecipe
from src.engine.contree_sandbox import ConTreeSandboxAdapter
from src.engine.token_factory_model import TokenFactoryModelAdapter
from src.preflight import verify_live_providers
from src.storage.db_client import RepoMedicDB
from src.storage.repository import D1StorageRepository
from src.worker import QueueWorker
from tests.test_storage import create_sqlite_d1_transport


@pytest.fixture
def live_pinned_recipe():
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


@pytest.mark.skipif(
    not os.getenv("REPOMEDIC_RUN_LIVE_PROVIDERS"),
    reason="Live provider smoke check is opt in; set REPOMEDIC_RUN_LIVE_PROVIDERS=true to execute",
)
@pytest.mark.asyncio
async def test_live_provider_smoke(live_pinned_recipe):
    """
    Operator opt in lightweight smoke check testing live provider endpoints,
    SDK operations, and sandbox startup without running a full repair pipeline.
    """
    token_factory_key = (
        os.getenv("TOKEN_FACTORY_API_KEY")
        or settings.token_factory_api_key
        or os.getenv("NEBIUS_API_KEY")
        or settings.nebius_api_key
        or ""
    ).strip()
    nebius_key = (os.getenv("NEBIUS_API_KEY") or settings.nebius_api_key or "").strip()
    project_id = (
        os.getenv("NEBIUS_PROJECT_ID")
        or settings.nebius_project_id
        or settings.token_factory_sandbox_project_id
        or ""
    ).strip()

    assert token_factory_key, "TOKEN_FACTORY_API_KEY must be configured for live test"
    assert nebius_key, "NEBIUS_API_KEY must be configured for live test"
    assert project_id, "NEBIUS_PROJECT_ID must be configured for live test"

    # 1. Preflight provider inspection
    preflight = verify_live_providers(
        repository_url=live_pinned_recipe.repository_url,
        commit_sha=live_pinned_recipe.commit_sha,
        timeout_seconds=live_pinned_recipe.timeout_seconds,
    )
    assert preflight.passed, f"Preflight checks failed: {preflight.errors}"

    # 2. Model ping
    model = TokenFactoryModelAdapter(
        api_key=token_factory_key,
        base_url=settings.token_factory_base_url,
        model=settings.token_factory_model,
        timeout_seconds=30.0,
    )
    prompt = "Ping response. Return the single word 'healthy'."
    response = await model.complete(prompt, max_tokens=10)
    assert len(response.strip()) > 0, "Model completion response must be non empty"

    # 3. Sandbox ping
    sandbox = ConTreeSandboxAdapter(
        api_key=nebius_key,
        project_id=project_id,
        base_image=settings.nebius_sandbox_image or "python:3.12-bookworm",
        timeout_seconds=60,
    )
    try:
        cmd_result = await sandbox.execute_command(["python", "--version"], timeout_seconds=30)
        assert cmd_result.exit_code == 0
        assert "Python" in (cmd_result.stdout + cmd_result.stderr)
    finally:
        await sandbox.cleanup()


@pytest.mark.skipif(
    not os.getenv("REPOMEDIC_RUN_LIVE_PROVIDERS"),
    reason="Live sequential repair acceptance is opt in; set REPOMEDIC_RUN_LIVE_PROVIDERS=true to execute",
)
@pytest.mark.asyncio
async def test_live_provider_successful_repair_acceptance(live_pinned_recipe, monkeypatch):
    """
    Operator opt in sequential repair acceptance test running through the full
    QueueWorker, D1HostPorts, and live engine path.
    A failed RepairResult must NOT satisfy this test.
    """
    monkeypatch.setattr(settings, "repomedic_mode", "live")
    monkeypatch.setattr(settings, "repomedic_max_run_usd", 2.0)
    monkeypatch.setattr(settings, "repomedic_total_budget_usd", 25.0)

    token_factory_key = (
        os.getenv("TOKEN_FACTORY_API_KEY")
        or settings.token_factory_api_key
        or os.getenv("NEBIUS_API_KEY")
        or settings.nebius_api_key
        or ""
    ).strip()
    nebius_key = (os.getenv("NEBIUS_API_KEY") or settings.nebius_api_key or "").strip()
    project_id = (
        os.getenv("NEBIUS_PROJECT_ID")
        or settings.nebius_project_id
        or settings.token_factory_sandbox_project_id
        or ""
    ).strip()

    assert token_factory_key, "TOKEN_FACTORY_API_KEY must be configured for live acceptance"
    assert nebius_key, "NEBIUS_API_KEY must be configured for live acceptance"
    assert project_id, "NEBIUS_PROJECT_ID must be configured for live acceptance"

    # Use SQLite D1 transport to test real D1StorageRepository persistence and HostPorts
    token = settings.repomedic_db_worker_token or settings.db_bridge_token or "dev-token"
    transport = create_sqlite_d1_transport(expected_token=token)
    db = RepoMedicDB(
        base_url="http://local-d1-bridge",
        api_key=token,
        transport=transport,
    )
    repo = D1StorageRepository(db)

    # Seed the recipe in the repository
    recipe_dict = {
        "test_command": live_pinned_recipe.test_command,
        "allowed_source_paths": live_pinned_recipe.allowed_source_paths,
        "expected_failure": live_pinned_recipe.expected_failure,
        "timeout_seconds": live_pinned_recipe.timeout_seconds,
        "max_candidates": live_pinned_recipe.max_candidates,
        "max_refinements": live_pinned_recipe.max_refinements,
    }
    repo.upsert_task({
        "task_id": live_pinned_recipe.task_id,
        "title": live_pinned_recipe.title,
        "repository_url": live_pinned_recipe.repository_url,
        "commit_sha": live_pinned_recipe.commit_sha,
        "dependency": live_pinned_recipe.dependency,
        "from_version": live_pinned_recipe.from_version,
        "to_version": live_pinned_recipe.to_version,
        "recipe_json": json.dumps(recipe_dict),
    })

    run_id = "run_k4_live_acceptance"
    repo.create_run(
        run_id=run_id,
        task_id=live_pinned_recipe.task_id,
        mode="live",
        search_mode="sequential",
        max_run_usd=2.0,
    )

    worker = QueueWorker(repo=repo, acceptance_prefix=run_id)
    processed = await worker.process_one()
    assert processed is True, "Worker must process queued run"

    run_record = repo.get_run(run_id)

    # CRITICAL: A failed repair result must not satisfy this acceptance test
    assert run_record.state == "succeeded", f"Live sequential repair must succeed, got state '{run_record.state}'"

    # Verify durable artifacts persisted through D1HostPorts
    artifacts = run_record.artifacts
    artifact_names = {a.filename for a in artifacts}
    assert "evidence.json" in artifact_names, "evidence.json artifact must be stored"
    assert "patch.diff" in artifact_names, "patch.diff artifact must be stored"
    assert "verify.log" in artifact_names, "verify.log artifact must be stored"

    for art in artifacts:
        content = repo.get_artifact_content(run_id, art.artifact_id)
        assert len(content) > 0, f"Artifact {art.filename} must contain non empty bytes"

    # Verify budget reservations in repository
    assert run_record.usage.estimated_usd <= 2.0, "Settled budget must not exceed 2.00 USD cap"
    budget_usage = repo.client.get_budget_usage()
    settled_micro = budget_usage.get("settled_micro_usd", 0)
    assert settled_micro <= 2_000_000, "Global settled budget must not exceed 2.00 USD cap for run"
