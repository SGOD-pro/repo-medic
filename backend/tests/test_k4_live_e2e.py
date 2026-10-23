import os
import pytest

from src.config import settings
from src.contracts import RepairRequest, TaskRecipe
from src.engine.contree_sandbox import ConTreeSandboxAdapter
from src.engine.repair import repair as engine_repair
from src.engine.token_factory_model import TokenFactoryModelAdapter
from src.storage.fake_host import FakeHost


@pytest.fixture
def live_pinned_recipe():
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


@pytest.mark.skipif(
    not os.getenv("REPOMEDIC_RUN_LIVE_PROVIDERS"),
    reason="Live provider test is opt in; set REPOMEDIC_RUN_LIVE_PROVIDERS=true to execute against live Nebius APIs",
)
@pytest.mark.asyncio
async def test_live_provider_sequential_repair_e2e(live_pinned_recipe):
    """
    Operator opt in live sequential repair test against Nebius Token Factory
    and ConTree remote containers.
    """
    token_factory_key = (
        os.getenv("TOKEN_FACTORY_API_KEY")
        or settings.token_factory_api_key
        or os.getenv("NEBIUS_API_KEY")
        or settings.nebius_api_key
    ).strip()
    nebius_key = (os.getenv("NEBIUS_API_KEY") or settings.nebius_api_key).strip()
    project_id = (
        os.getenv("NEBIUS_PROJECT_ID")
        or settings.nebius_project_id
        or settings.token_factory_sandbox_project_id
    ).strip()

    assert token_factory_key, "TOKEN_FACTORY_API_KEY must be configured for live test"
    assert nebius_key, "NEBIUS_API_KEY must be configured for live test"
    assert project_id, "NEBIUS_PROJECT_ID must be configured for live test"

    request = RepairRequest(
        run_id="run_live_e2e_opt_in",
        task_id=live_pinned_recipe.task_id,
        mode="live",
        search_mode="sequential",
        max_run_usd=2.0,
    )

    host = FakeHost()
    sandbox = ConTreeSandboxAdapter(
        api_key=nebius_key,
        project_id=project_id,
        base_image=settings.nebius_sandbox_image or "python:3.12-bookworm",
        timeout_seconds=600,
    )
    model = TokenFactoryModelAdapter(
        api_key=token_factory_key,
        base_url=settings.token_factory_base_url,
        model=settings.token_factory_model,
    )

    try:
        result = await engine_repair(
            request=request,
            recipe=live_pinned_recipe,
            host=host,
            sandbox=sandbox,
            model=model,
        )
        assert result.state in ("succeeded", "failed")
        # Assert budget settlement stayed strictly bounded under cap
        total_spent = sum(host.settlements.values())
        assert total_spent <= 2.0
    finally:
        await sandbox.cleanup()
