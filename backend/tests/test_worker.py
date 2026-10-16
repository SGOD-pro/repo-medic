import asyncio
import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.contracts import RepairResult, TaskRecipe
from src.engine import fake_engine
from src.main import create_app
from src.storage.db_client import RepoMedicDB
from src.storage.repository import D1StorageRepository
from src.worker import QueueWorker, load_task_recipe, run_standalone
from tests.test_storage import create_sqlite_d1_transport


@pytest.fixture
def test_repo() -> D1StorageRepository:
    transport = create_sqlite_d1_transport(expected_token="test-bridge-token")
    mock_db = RepoMedicDB(
        base_url="http://test-bridge",
        api_key="test-bridge-token",
        transport=transport,
    )
    return D1StorageRepository(mock_db)


def test_load_task_recipe_from_d1_recipe_json(test_repo: D1StorageRepository) -> None:
    recipe_dict = {
        "test_command": ["pytest", "tests/unit"],
        "allowed_source_paths": ["src/", "pkg/"],
        "expected_failure": "ZeroDivisionError",
        "timeout_seconds": 300,
        "max_candidates": 2,
        "max_refinements": 0,
    }
    test_repo.upsert_task({
        "task_id": "task-with-json",
        "title": "Fix math zero division",
        "repository_url": "https://github.com/example/math",
        "commit_sha": "abc12345",
        "dependency": "mathlib",
        "from_version": "1.0",
        "to_version": "1.1",
        "recipe_json": json.dumps(recipe_dict),
    })

    recipe = load_task_recipe("task-with-json", test_repo)
    assert isinstance(recipe, TaskRecipe)
    assert recipe.task_id == "task-with-json"
    assert recipe.test_command == ["pytest", "tests/unit"]
    assert recipe.allowed_source_paths == ["src/", "pkg/"]
    assert recipe.expected_failure == "ZeroDivisionError"
    assert recipe.timeout_seconds == 300
    assert recipe.max_candidates == 2
    assert recipe.max_refinements == 0


def test_load_task_recipe_from_fixture_file(test_repo: D1StorageRepository) -> None:
    recipe = load_task_recipe("example-task-1", test_repo)
    assert isinstance(recipe, TaskRecipe)
    assert recipe.task_id == "example-task-1"
    assert recipe.dependency == "pytest-mock"
    assert recipe.expected_failure == "AssertionError"
    assert recipe.test_command == ["pytest", "tests/"]


def test_load_task_recipe_fallback_default(test_repo: D1StorageRepository) -> None:
    test_repo.upsert_task({
        "task_id": "task-unknown-recipe",
        "title": "Upgrade requests library",
        "repository_url": "https://github.com/example/req",
        "commit_sha": "def67890",
        "dependency": "requests",
        "from_version": "2.28.0",
        "to_version": "2.31.0",
    })

    recipe = load_task_recipe("task-unknown-recipe", test_repo)
    assert isinstance(recipe, TaskRecipe)
    assert recipe.task_id == "task-unknown-recipe"
    assert recipe.test_command == ["pytest", "tests/"]
    assert recipe.expected_failure == "AssertionError"
    assert recipe.allowed_source_paths == ["src/"]


@pytest.mark.asyncio
async def test_queue_worker_process_one_success(test_repo: D1StorageRepository) -> None:
    test_repo.upsert_task({
        "task_id": "example-task-1",
        "title": "Upgrade pytest-mock",
        "repository_url": "https://github.com/example/repo",
        "commit_sha": "abcdef123456",
        "dependency": "pytest-mock",
        "from_version": "3.10.0",
        "to_version": "3.11.1",
    })

    run_id = "run-worker-test-1"
    test_repo.create_run(
        run_id=run_id,
        task_id="example-task-1",
        mode="offline",
        search_mode="branch_refine",
        state="queued",
    )

    worker = QueueWorker(repo=test_repo, poll_interval_seconds=0.01)
    processed = await worker.process_one()
    assert processed is True

    # Check terminal state in D1
    run = test_repo.get_run(run_id)
    assert run.state == "succeeded"

    # Verify run.finished event emitted
    events = test_repo.list_events(run_id)
    event_types = [e.type for e in events]
    assert "stage.completed" in event_types
    assert "candidate.completed" in event_types
    assert "usage.updated" in event_types
    assert "run.finished" in event_types

    finish_event = next(e for e in events if e.type == "run.finished")
    assert finish_event.payload.get("state") == "succeeded"


@pytest.mark.asyncio
async def test_queue_worker_process_one_empty_queue(test_repo: D1StorageRepository) -> None:
    worker = QueueWorker(repo=test_repo, poll_interval_seconds=0.01)
    processed = await worker.process_one()
    assert processed is False


@pytest.mark.asyncio
async def test_queue_worker_fifo_ordering(test_repo: D1StorageRepository) -> None:
    test_repo.upsert_task({
        "task_id": "example-task-1",
        "title": "Upgrade pytest-mock",
        "repository_url": "https://github.com/example/repo",
        "commit_sha": "abcdef123456",
        "dependency": "pytest-mock",
        "from_version": "3.10.0",
        "to_version": "3.11.1",
    })

    test_repo.create_run(
        run_id="run-fifo-1",
        task_id="example-task-1",
        mode="offline",
        search_mode="branch_refine",
        state="queued",
        created_at="2026-10-10T10:00:00Z",
    )
    test_repo.create_run(
        run_id="run-fifo-2",
        task_id="example-task-1",
        mode="offline",
        search_mode="branch_refine",
        state="queued",
        created_at="2026-10-10T10:05:00Z",
    )

    worker = QueueWorker(repo=test_repo, poll_interval_seconds=0.01)

    # First execution should claim run-fifo-1
    processed_1 = await worker.process_one()
    assert processed_1 is True
    assert test_repo.get_run("run-fifo-1").state == "succeeded"
    assert test_repo.get_run("run-fifo-2").state == "queued"

    # Second execution should claim run-fifo-2
    processed_2 = await worker.process_one()
    assert processed_2 is True
    assert test_repo.get_run("run-fifo-2").state == "succeeded"


@pytest.mark.asyncio
async def test_queue_worker_unhandled_exception(test_repo: D1StorageRepository) -> None:
    test_repo.upsert_task({
        "task_id": "example-task-1",
        "title": "Upgrade pytest-mock",
        "repository_url": "https://github.com/example/repo",
        "commit_sha": "abcdef123456",
        "dependency": "pytest-mock",
        "from_version": "3.10.0",
        "to_version": "3.11.1",
    })

    run_id = "run-error-test"
    test_repo.create_run(
        run_id=run_id,
        task_id="example-task-1",
        mode="offline",
        search_mode="branch_refine",
        state="queued",
    )

    worker = QueueWorker(repo=test_repo, poll_interval_seconds=0.01)

    with patch.object(
        fake_engine,
        "repair",
        AsyncMock(side_effect=RuntimeError("Sandbox crash simulation")),
    ):
        processed = await worker.process_one()
        assert processed is True

    run = test_repo.get_run(run_id)
    assert run.state == "failed"
    assert run.reason is not None
    assert "Sandbox crash simulation" in run.reason

    events = test_repo.list_events(run_id)
    finish_event = next((e for e in events if e.type == "run.finished"), None)
    assert finish_event is not None
    assert finish_event.payload.get("state") == "failed"


@pytest.mark.asyncio
async def test_queue_worker_concurrent_claim_cas(test_repo: D1StorageRepository) -> None:
    test_repo.upsert_task({
        "task_id": "example-task-1",
        "title": "Upgrade pytest-mock",
        "repository_url": "https://github.com/example/repo",
        "commit_sha": "abcdef123456",
        "dependency": "pytest-mock",
        "from_version": "3.10.0",
        "to_version": "3.11.1",
    })

    run_id = "run-cas-compete"
    test_repo.create_run(
        run_id=run_id,
        task_id="example-task-1",
        mode="offline",
        search_mode="sequential",
        state="queued",
    )

    worker1 = QueueWorker(repo=test_repo)
    worker2 = QueueWorker(repo=test_repo)

    # Simulate worker 1 claiming first
    p1 = await worker1.process_one()
    assert p1 is True

    # Run is now in succeeded terminal state; worker 2 attempting to claim gets 409 and skips
    p2 = await worker2.process_one()
    assert p2 is False


@pytest.mark.asyncio
async def test_queue_worker_per_run_budget(test_repo: D1StorageRepository) -> None:
    test_repo.upsert_task({
        "task_id": "example-task-1",
        "title": "Upgrade pytest-mock",
        "repository_url": "https://github.com/example/repo",
        "commit_sha": "abcdef123456",
        "dependency": "pytest-mock",
        "from_version": "3.10.0",
        "to_version": "3.11.1",
    })

    run_id = "run-budget-test"
    test_repo.create_run(
        run_id=run_id,
        task_id="example-task-1",
        mode="offline",
        search_mode="sequential",
        max_run_usd=3.5,
        state="queued",
    )

    worker = QueueWorker(repo=test_repo)
    captured_request = []

    async def mock_repair(req, recipe, host):
        captured_request.append(req)
        return RepairResult(state="succeeded", reason="Budget verified")

    with patch.object(fake_engine, "repair", mock_repair):
        processed = await worker.process_one()
        assert processed is True

    assert len(captured_request) == 1
    assert captured_request[0].max_run_usd == 3.5


def test_find_task_fixture_dir_fallback() -> None:
    from src.fixtures import find_task_fixture_dir
    # Normal execution finds fixture directory
    d = find_task_fixture_dir()
    assert d is not None

    # When all candidates are missing, returns None
    with patch("pathlib.Path.is_dir", return_value=False):
        assert find_task_fixture_dir() is None


@pytest.mark.asyncio
async def test_queue_worker_start_stop_lifecycle(test_repo: D1StorageRepository) -> None:
    worker = QueueWorker(repo=test_repo, poll_interval_seconds=0.01)
    assert worker._running is False

    await worker.start()
    assert worker._running is True
    assert worker._loop_task is not None

    # Idempotent start
    await worker.start()
    assert worker._running is True

    await worker.stop()
    assert worker._running is False
    assert worker._loop_task is None


@pytest.mark.asyncio
async def test_run_standalone_max_runs(test_repo: D1StorageRepository) -> None:
    test_repo.upsert_task({
        "task_id": "example-task-1",
        "title": "Upgrade pytest-mock",
        "repository_url": "https://github.com/example/repo",
        "commit_sha": "abcdef123456",
        "dependency": "pytest-mock",
        "from_version": "3.10.0",
        "to_version": "3.11.1",
    })

    test_repo.create_run(
        run_id="run-standalone-1",
        task_id="example-task-1",
        mode="offline",
        search_mode="branch_refine",
        state="queued",
    )

    await run_standalone(repo=test_repo, max_runs=1)
    run = test_repo.get_run("run-standalone-1")
    assert run.state == "succeeded"


@pytest.mark.asyncio
async def test_run_standalone_max_runs_zero(test_repo: D1StorageRepository) -> None:
    test_repo.upsert_task({
        "task_id": "example-task-1",
        "title": "Upgrade pytest-mock",
        "repository_url": "https://github.com/example/repo",
        "commit_sha": "abcdef123456",
        "dependency": "pytest-mock",
        "from_version": "3.10.0",
        "to_version": "3.11.1",
    })

    test_repo.create_run(
        run_id="run-standalone-zero",
        task_id="example-task-1",
        mode="offline",
        search_mode="branch_refine",
        state="queued",
    )

    await run_standalone(repo=test_repo, max_runs=0)
    run = test_repo.get_run("run-standalone-zero")
    assert run.state == "queued"


@pytest.mark.asyncio
async def test_fastapi_lifespan_worker_integration(test_repo: D1StorageRepository) -> None:
    worker = QueueWorker(repo=test_repo, poll_interval_seconds=0.01)
    app = create_app(repository=test_repo, worker=worker)

    async with app.router.lifespan_context(app):
        assert worker._running is True

    assert worker._running is False


@pytest.mark.asyncio
async def test_finish_run_event_failure_does_not_propagate(test_repo: D1StorageRepository) -> None:
    """If append_event fails after update_run_state succeeds, finish_run must not
    re-raise the error. The run must still be in the terminal state, and no
    second finish_run call should follow (which would produce a duplicate event)."""
    test_repo.create_run(
        run_id="run-finish-resilience",
        task_id="example-task-1",
        mode="offline",
        search_mode="sequential",
        state="running",
    )

    append_call_count = [0]

    def failing_append(run_id, event_type, payload):
        append_call_count[0] += 1
        raise httpx.RequestError("Simulated bridge outage")

    with patch.object(test_repo, "append_event", side_effect=failing_append):
        # finish_run must not raise even when append_event fails
        test_repo.finish_run("run-finish-resilience", state="succeeded", reason="done")

    # State was persisted despite the event failure
    run = test_repo.get_run("run-finish-resilience")
    assert run.state == "succeeded"
    # append_event was attempted exactly once (no double-finish loop)
    assert append_call_count[0] == 1


@pytest.mark.asyncio
async def test_finish_run_programming_error_propagates(test_repo: D1StorageRepository) -> None:
    """Non-network programming bugs in append_event (e.g. AttributeError) must propagate
    rather than being silently swallowed."""
    test_repo.create_run(
        run_id="run-finish-prog-error",
        task_id="example-task-1",
        mode="offline",
        search_mode="sequential",
        state="running",
    )

    def bug_append(run_id, event_type, payload):
        raise AttributeError("Simulated programming bug inside append_event")

    with patch.object(test_repo, "append_event", side_effect=bug_append):
        with pytest.raises(AttributeError, match="Simulated programming bug"):
            test_repo.finish_run("run-finish-prog-error", state="succeeded", reason="done")


@pytest.mark.asyncio
async def test_non_cas_patch_rejects_terminal_state_overwrite(test_repo: D1StorageRepository) -> None:
    """A non-CAS PATCH (no from_state) must not silently overwrite a run that
    has already reached a terminal state. The bridge should return 409."""
    test_repo.create_run(
        run_id="run-non-cas-guard",
        task_id="example-task-1",
        mode="offline",
        search_mode="sequential",
        state="running",
    )
    # First caller: transition to succeeded
    test_repo.update_run_state("run-non-cas-guard", state="succeeded", reason="first")

    # Second caller: attempt to overwrite without from_state should fail with 409
    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        test_repo.update_run_state("run-non-cas-guard", state="failed", reason="second")
    assert exc_info.value.response.status_code == 409

    # State must still be succeeded
    run = test_repo.get_run("run-non-cas-guard")
    assert run.state == "succeeded"
    assert run.reason == "first"


@pytest.mark.asyncio
async def test_process_one_finish_run_programming_error_does_not_double_finish(
    test_repo: D1StorageRepository,
) -> None:
    """When finish_run raises a programming error in process_one, the worker must not
    attempt a second finish_run('failed') call that would trigger a 409 conflict
    or overwrite the terminal state."""
    test_repo.upsert_task({
        "task_id": "example-task-1",
        "title": "Upgrade pytest-mock",
        "repository_url": "https://github.com/example/repo",
        "commit_sha": "abcdef123456",
        "dependency": "pytest-mock",
        "from_version": "3.10.0",
        "to_version": "3.11.1",
    })

    run_id = "run-double-finish-guard"
    test_repo.create_run(
        run_id=run_id,
        task_id="example-task-1",
        mode="offline",
        search_mode="sequential",
        state="queued",
    )

    worker = QueueWorker(repo=test_repo, poll_interval_seconds=0.01)

    finish_calls: list[str] = []
    original_finish_run = test_repo.finish_run

    def tracked_finish_run(rid: str, state: str, reason: str | None = None) -> None:
        finish_calls.append(state)
        # Call original finish_run which updates state to 'succeeded'
        original_finish_run(rid, state=state, reason=reason)
        # Then simulate an uncaught post-state-update bug
        raise AttributeError("Simulated post-state-update bug")

    with patch.object(test_repo, "finish_run", side_effect=tracked_finish_run):
        with pytest.raises(AttributeError, match="Simulated post-state-update bug"):
            await worker.process_one()

    # finish_run was called only once (for succeeded), not a second time for failed
    assert finish_calls == ["succeeded"]
    # Run in D1 is in succeeded state
    run = test_repo.get_run(run_id)
    assert run.state == "succeeded"


@pytest.mark.asyncio
async def test_process_one_terminal_state_conflict_handled_gracefully(
    test_repo: D1StorageRepository,
) -> None:
    """If a run is concurrently cancelled or transitioned to a terminal state while
    the engine executes, finish_run encountering a 409 conflict is handled cleanly."""
    test_repo.upsert_task({
        "task_id": "example-task-1",
        "title": "Upgrade pytest-mock",
        "repository_url": "https://github.com/example/repo",
        "commit_sha": "abcdef123456",
        "dependency": "pytest-mock",
        "from_version": "3.10.0",
        "to_version": "3.11.1",
    })

    run_id = "run-concurrent-cancel"
    test_repo.create_run(
        run_id=run_id,
        task_id="example-task-1",
        mode="offline",
        search_mode="sequential",
        state="queued",
    )

    worker = QueueWorker(repo=test_repo, poll_interval_seconds=0.01)

    # Simulate concurrent cancellation while repair is executing
    async def cancelling_repair(req, rec, host):
        test_repo.update_run_state(run_id, state="cancelled", reason="user cancelled")
        return RepairResult(run_id=run_id, state="succeeded", reason="done")

    with patch.object(fake_engine, "repair", side_effect=cancelling_repair):
        processed = await worker.process_one()
        assert processed is True

    # State remains cancelled (terminal state was not overwritten, and no unhandled 409)
    run = test_repo.get_run(run_id)
    assert run.state == "cancelled"


@pytest.mark.asyncio
async def test_queue_worker_wires_engine_repair(test_repo: D1StorageRepository) -> None:
    test_repo.upsert_task({
        "task_id": "example-task-1",
        "title": "Upgrade pytest-mock",
        "repository_url": "https://github.com/example/repo",
        "commit_sha": "abcdef123456",
        "dependency": "pytest-mock",
        "from_version": "3.10.0",
        "to_version": "3.11.1",
    })

    run_id = "run-engine-wired"
    test_repo.create_run(
        run_id=run_id,
        task_id="example-task-1",
        mode="offline",
        search_mode="sequential",
        state="queued",
    )

    calls = []

    async def mock_engine_repair(req, recipe, host):
        calls.append(req.run_id)
        return RepairResult(state="succeeded", reason="Engine repair verified")

    worker = QueueWorker(repo=test_repo, use_real_engine=True, repair_fn=mock_engine_repair)
    processed = await worker.process_one()
    assert processed is True
    assert calls == ["run-engine-wired"]
    run = test_repo.get_run(run_id)
    assert run.state == "succeeded"
