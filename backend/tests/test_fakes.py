import pytest
import asyncio
import json
from pydantic import ValidationError
from src.contracts import (
    RepairRequest,
    TaskRecipe,
    RunSummary,
    RunHistoryItem,
    ReconnectResult,
    EventEnvelope,
    UsageSummary,
)
from src.engine.fake_engine import repair
from src.storage.fake_host import FakeHost


@pytest.fixture
def dummy_request():
    return RepairRequest(
        run_id="test-run",
        task_id="test-task",
        mode="offline",
        search_mode="sequential",
        max_run_usd=1.0,
    )


@pytest.fixture
def dummy_recipe():
    return TaskRecipe(
        task_id="test-task",
        title="Test Task Title",
        repository_url="https://github.com/example/repo",
        commit_sha="abcdef123456",
        dependency="pytest-mock",
        from_version="3.10.0",
        to_version="3.11.1",
        test_command=["pytest"],
        allowed_source_paths=["src/"],
        expected_failure="Error",
        timeout_seconds=60,
        max_candidates=1,
        max_refinements=0,
    )


@pytest.mark.asyncio
async def test_repair_success(dummy_request, dummy_recipe):
    host = FakeHost()
    result = await repair(dummy_request, dummy_recipe, host)
    assert result.state == "succeeded"
    assert len(host.events) > 0
    assert "model:1" in host.reservations
    assert "model:1" in host.settlements

    # Verify FakeEngine emits supported engine events
    event_types = [e["type"] for e in host.events]
    assert "stage.completed" in event_types
    assert "usage.updated" in event_types
    assert "candidate.completed" in event_types
    # Verify FakeEngine never emits run.finished (B owns run.finished)
    assert "run.finished" not in event_types

    # Verify each emitted event is valid against EventEnvelope
    for i, e in enumerate(host.events, 1):
        env = EventEnvelope(
            run_id=dummy_request.run_id,
            seq=i,
            ts="2026-10-09T00:00:00Z",
            type=e["type"],
            payload=e["payload"],
        )
        assert env.type == e["type"]


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
    # 1. Task recipe
    with open('../fixtures/tasks/example-task-1.json') as f:
        TaskRecipe.model_validate_json(f.read())

    # 2. Documented runs
    with open('../fixtures/runs/success.json') as f:
        run = RunSummary.model_validate_json(f.read())
        assert run.state == "succeeded"
        assert run.reason is None
        assert run.usage.estimated_usd >= 0.0

    with open('../fixtures/runs/failure.json') as f:
        run = RunSummary.model_validate_json(f.read())
        assert run.state == "failed"
        assert run.reason == "Baseline check failed"

    with open('../fixtures/runs/cancel.json') as f:
        run = RunSummary.model_validate_json(f.read())
        assert run.state == "cancelled"

    with open('../fixtures/runs/queued.json') as f:
        run = RunSummary.model_validate_json(f.read())
        assert run.state == "queued"
        assert run.reason is None

    # 3. Events / reconnect
    with open('../fixtures/runs/reconnect.json') as f:
        rec = ReconnectResult.model_validate_json(f.read())
        assert len(rec.events) == 4

    # 4. History
    with open('../fixtures/runs/history.json') as f:
        data = json.load(f)
        for item in data:
            RunHistoryItem.model_validate(item)


def test_negative_validations():
    # Missing required field
    with pytest.raises(ValidationError):
        RunSummary.model_validate({
            "task_id": "t1",
            "mode": "offline",
            "search_mode": "sequential",
            "state": "queued",
            "usage": {"model_calls": 0, "input_tokens": 0, "output_tokens": 0, "estimated_usd": 0},
            "artifacts": []
        })

    # Invalid state
    with pytest.raises(ValidationError):
        RunSummary.model_validate({
            "run_id": "r1",
            "task_id": "t1",
            "mode": "offline",
            "search_mode": "sequential",
            "state": "flying",
            "usage": {"model_calls": 0, "input_tokens": 0, "output_tokens": 0, "estimated_usd": 0},
            "artifacts": []
        })

    # Invalid search_mode
    with pytest.raises(ValidationError):
        RunSummary.model_validate({
            "run_id": "r1",
            "task_id": "t1",
            "mode": "offline",
            "search_mode": "quantum",
            "state": "queued",
            "usage": {"model_calls": 0, "input_tokens": 0, "output_tokens": 0, "estimated_usd": 0},
            "artifacts": []
        })

    # Negative usage value
    with pytest.raises(ValidationError):
        UsageSummary(model_calls=-1, input_tokens=0, output_tokens=0, estimated_usd=0.0)

    # Invalid event sequence (seq < 1)
    with pytest.raises(ValidationError):
        EventEnvelope(
            run_id="r1",
            seq=0,
            ts="2026-10-09T00:00:00Z",
            type="run.started",
            payload={"mode": "offline", "search_mode": "sequential", "max_run_usd": 1.0}
        )

    # Invalid event type
    with pytest.raises(ValidationError):
        EventEnvelope(
            run_id="r1",
            seq=1,
            ts="2026-10-09T00:00:00Z",
            type="magic.completed",
            payload={"summary": "test"}
        )

    # Per-event payload negative validations
    # 1. run.started
    with pytest.raises(ValidationError):
        EventEnvelope(run_id="r1", seq=1, ts="2026-10-09T00:00:00Z", type="run.started", payload={})
    with pytest.raises(ValidationError):
        EventEnvelope(
            run_id="r1", seq=1, ts="2026-10-09T00:00:00Z", type="run.started",
            payload={"mode": "invalid", "search_mode": "sequential", "max_run_usd": 1.0}
        )

    # 2. stage.completed
    with pytest.raises(ValidationError):
        EventEnvelope(run_id="r1", seq=1, ts="2026-10-09T00:00:00Z", type="stage.completed", payload={})
    with pytest.raises(ValidationError):
        EventEnvelope(
            run_id="r1", seq=1, ts="2026-10-09T00:00:00Z", type="stage.completed",
            payload={"stage": "invalid_stage", "passed": True, "summary": "msg"}
        )

    # 3. candidate.completed
    with pytest.raises(ValidationError):
        EventEnvelope(run_id="r1", seq=1, ts="2026-10-09T00:00:00Z", type="candidate.completed", payload={})
    with pytest.raises(ValidationError):
        EventEnvelope(
            run_id="r1", seq=1, ts="2026-10-09T00:00:00Z", type="candidate.completed",
            payload={"candidate_id": 123, "passed": "not_bool", "summary": "msg"}
        )

    # 4. usage.updated
    with pytest.raises(ValidationError):
        EventEnvelope(run_id="r1", seq=1, ts="2026-10-09T00:00:00Z", type="usage.updated", payload={})
    with pytest.raises(ValidationError):
        EventEnvelope(
            run_id="r1", seq=1, ts="2026-10-09T00:00:00Z", type="usage.updated",
            payload={"model_calls": -1, "input_tokens": 0, "output_tokens": 0, "estimated_usd": 0.0}
        )

    # 5. run.finished
    with pytest.raises(ValidationError):
        EventEnvelope(run_id="r1", seq=1, ts="2026-10-09T00:00:00Z", type="run.finished", payload={})
    with pytest.raises(ValidationError):
        EventEnvelope(
            run_id="r1", seq=1, ts="2026-10-09T00:00:00Z", type="run.finished",
            payload={"state": "queued", "reason": None}
        )
