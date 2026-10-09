import pytest
import asyncio
import json
from src.contracts import RepairRequest, TaskRecipe, RunDetail, RunHistoryItem, ReconnectResult
from src.engine.fake_engine import repair
from src.storage.fake_host import FakeHost

@pytest.fixture
def dummy_request():
    return RepairRequest(
        run_id="test-run",
        task_id="test-task",
        mode="offline",
        search_mode="sequential",
        max_run_usd=1.0
    )

@pytest.fixture
def dummy_recipe():
    return TaskRecipe(
        task_id="test-task",
        repository="foo",
        commit="bar",
        test_command=["pytest"],
        allowed_source_paths=["src/"],
        expected_failure="Error",
        timeout_seconds=60,
        max_candidates=1,
        max_refinements=0
    )

@pytest.mark.asyncio
async def test_repair_success(dummy_request, dummy_recipe):
    host = FakeHost()
    result = await repair(dummy_request, dummy_recipe, host)
    assert result.state == "succeeded"
    assert len(host.events) > 0
    assert "model:1" in host.reservations
    assert "model:1" in host.settlements

@pytest.mark.asyncio
async def test_repair_cancelled(dummy_request, dummy_recipe):
    host = FakeHost()
    host.is_cancelled = True
    result = await repair(dummy_request, dummy_recipe, host)
    assert result.state == "cancelled"

@pytest.mark.asyncio
async def test_repair_budget_denial(dummy_request, dummy_recipe):
    class DenyingHost(FakeHost):
        async def reserve(self, operation_id: str, estimated_usd: float) -> bool:
            return False
            
    host = DenyingHost()
    result = await repair(dummy_request, dummy_recipe, host)
    assert result.state == "failed"
    assert result.reason == "Budget denied"

def test_fixtures_validation():
    with open('../fixtures/tasks/example-task-1.json') as f:
        TaskRecipe.model_validate_json(f.read())
        
    with open('../fixtures/runs/success.json') as f:
        RunDetail.model_validate_json(f.read())

    with open('../fixtures/runs/failure.json') as f:
        RunDetail.model_validate_json(f.read())

    with open('../fixtures/runs/cancel.json') as f:
        RunDetail.model_validate_json(f.read())

    with open('../fixtures/runs/reconnect.json') as f:
        ReconnectResult.model_validate_json(f.read())

    with open('../fixtures/runs/history.json') as f:
        data = json.load(f)
        for item in data:
            RunHistoryItem.model_validate(item)
