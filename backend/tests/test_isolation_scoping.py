import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.contracts import RepairRequest, RepairResult, TaskRecipe
from src.main import create_app, recover_interrupted_runs, sync_task_fixtures
from src.storage.db_client import RepoMedicDB
from src.storage.repository import D1StorageRepository
from src.worker import QueueWorker
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


def test_sync_task_fixtures_disabled_gate(test_repo: D1StorageRepository) -> None:
    """When sync_enabled is False, no task fixtures are inserted."""
    sync_task_fixtures(test_repo, sync_enabled=False)
    tasks = test_repo.list_tasks()
    assert len(tasks) == 0


def test_sync_task_fixtures_with_acceptance_prefix(
    test_repo: D1StorageRepository,
    tmp_path: Path,
) -> None:
    """When acceptance_prefix is provided, only matching task fixtures are synced."""
    # Create temporary fixture files
    match_fixture = {
        "task_id": "accept_task_1",
        "title": "Matching acceptance task",
        "repository_url": "https://github.com/example/repo",
        "commit_sha": "abc123",
        "dependency": "pkg-a",
        "from_version": "1.0",
        "to_version": "2.0",
    }
    other_fixture = {
        "task_id": "other_task_2",
        "title": "Unrelated task",
        "repository_url": "https://github.com/example/repo",
        "commit_sha": "def456",
        "dependency": "pkg-b",
        "from_version": "1.0",
        "to_version": "2.0",
    }
    (tmp_path / "accept_task_1.json").write_text(json.dumps(match_fixture), encoding="utf-8")
    (tmp_path / "other_task_2.json").write_text(json.dumps(other_fixture), encoding="utf-8")

    with patch("src.main.find_task_fixture_dir", return_value=tmp_path):
        sync_task_fixtures(test_repo, sync_enabled=True, acceptance_prefix="accept_")

    tasks = test_repo.list_tasks()
    task_ids = [t.task_id for t in tasks]
    assert "accept_task_1" in task_ids
    assert "other_task_2" not in task_ids


def test_recover_interrupted_runs_scoped(test_repo: D1StorageRepository) -> None:
    """When acceptance_prefix is set, only matching running runs are failed."""
    # Pre populate task
    test_repo.upsert_task({
        "task_id": "task_1",
        "title": "Test task",
        "repository_url": "https://github.com/example/repo",
        "commit_sha": "abc123",
        "dependency": "pkg",
        "from_version": "1.0",
        "to_version": "2.0",
    })

    # Create two runs: one scoped, one unrelated
    test_repo.create_run(
        run_id="run_k3_accept_1",
        task_id="task_1",
        mode="offline",
        search_mode="sequential",
        state="running",
    )
    test_repo.create_run(
        run_id="run_unrelated_2",
        task_id="task_1",
        mode="offline",
        search_mode="sequential",
        state="running",
    )

    # Run recovery with prefix scoping
    recover_interrupted_runs(test_repo, acceptance_prefix="run_k3_accept_")

    # Scoped run must be transitioned to failed
    scoped_run = test_repo.get_run("run_k3_accept_1")
    assert scoped_run.state == "failed"
    assert "restarted" in (scoped_run.reason or "")

    # Unrelated run must remain in running state
    unrelated_run = test_repo.get_run("run_unrelated_2")
    assert unrelated_run.state == "running"


def test_recover_interrupted_runs_unscoped(test_repo: D1StorageRepository) -> None:
    """When acceptance_prefix is empty, all running runs are failed."""
    test_repo.upsert_task({
        "task_id": "task_1",
        "title": "Test task",
        "repository_url": "https://github.com/example/repo",
        "commit_sha": "abc123",
        "dependency": "pkg",
        "from_version": "1.0",
        "to_version": "2.0",
    })
    test_repo.create_run(
        run_id="run_1",
        task_id="task_1",
        mode="offline",
        search_mode="sequential",
        state="running",
    )
    test_repo.create_run(
        run_id="run_2",
        task_id="task_1",
        mode="offline",
        search_mode="sequential",
        state="running",
    )

    recover_interrupted_runs(test_repo, acceptance_prefix="")

    assert test_repo.get_run("run_1").state == "failed"
    assert test_repo.get_run("run_2").state == "failed"


@pytest.mark.asyncio
async def test_queue_worker_claims_only_matching_prefix(test_repo: D1StorageRepository) -> None:
    """QueueWorker claims only queued runs matching acceptance_prefix, skipping others."""
    test_repo.upsert_task({
        "task_id": "task_1",
        "title": "Test task",
        "repository_url": "https://github.com/example/repo",
        "commit_sha": "abc123",
        "dependency": "pkg",
        "from_version": "1.0",
        "to_version": "2.0",
    })

    # Insert an unrelated queued run first
    test_repo.create_run(
        run_id="run_other_first",
        task_id="task_1",
        mode="offline",
        search_mode="sequential",
        state="queued",
        created_at="2026-10-18T10:00:00Z",
    )

    # Insert a matching queued run second
    test_repo.create_run(
        run_id="run_k3_accept_target",
        task_id="task_1",
        mode="offline",
        search_mode="sequential",
        state="queued",
        created_at="2026-10-18T10:01:00Z",
    )

    async def mock_repair(req: RepairRequest, recipe: TaskRecipe, host: object) -> RepairResult:
        return RepairResult(state="succeeded", reason="Repaired target run")

    worker = QueueWorker(
        repo=test_repo,
        repair_fn=mock_repair,
        acceptance_prefix="run_k3_accept_",
    )

    # Process one run
    processed = await worker.process_one()
    assert processed is True

    # Matching run must have been claimed and processed
    target_run = test_repo.get_run("run_k3_accept_target")
    assert target_run.state == "succeeded"

    # Unrelated run must remain queued and untouched
    other_run = test_repo.get_run("run_other_first")
    assert other_run.state == "queued"


@pytest.mark.asyncio
async def test_queue_worker_finds_matching_run_beyond_first_100_unrelated_rows(
    test_repo: D1StorageRepository,
) -> None:
    """QueueWorker claims matching run even when preceded by more than 100 unrelated runs."""
    test_repo.upsert_task({
        "task_id": "task_1",
        "title": "Test task",
        "repository_url": "https://github.com/example/repo",
        "commit_sha": "abc123",
        "dependency": "pkg",
        "from_version": "1.0",
        "to_version": "2.0",
    })

    # Insert 105 unrelated queued runs first
    for i in range(105):
        test_repo.create_run(
            run_id=f"run_unrelated_{i:03d}",
            task_id="task_1",
            mode="offline",
            search_mode="sequential",
            state="queued",
            created_at=f"2026-10-18T00:{i // 60:02d}:{i % 60:02d}Z",
        )

    # Insert the matching run at position 106
    test_repo.create_run(
        run_id="run_k3_accept_hidden_target",
        task_id="task_1",
        mode="offline",
        search_mode="sequential",
        state="queued",
        created_at="2026-10-18T02:00:00Z",
    )

    async def mock_repair(req: RepairRequest, recipe: TaskRecipe, host: object) -> RepairResult:
        return RepairResult(state="succeeded", reason="Repaired hidden target run")

    worker = QueueWorker(
        repo=test_repo,
        repair_fn=mock_repair,
        acceptance_prefix="run_k3_accept_",
    )

    processed = await worker.process_one()
    assert processed is True

    target_run = test_repo.get_run("run_k3_accept_hidden_target")
    assert target_run.state == "succeeded"

    # Verify unrelated runs are still queued
    assert test_repo.get_run("run_unrelated_000").state == "queued"
    assert test_repo.get_run("run_unrelated_104").state == "queued"


def test_recover_interrupted_runs_finds_matching_runs_beyond_first_100_unrelated_rows(
    test_repo: D1StorageRepository,
) -> None:
    """Interrupted recovery marks matching runs even when preceded by more than 100 unrelated runs."""
    test_repo.upsert_task({
        "task_id": "task_1",
        "title": "Test task",
        "repository_url": "https://github.com/example/repo",
        "commit_sha": "abc123",
        "dependency": "pkg",
        "from_version": "1.0",
        "to_version": "2.0",
    })

    # Insert 105 unrelated running runs first
    for i in range(105):
        test_repo.create_run(
            run_id=f"run_unrelated_running_{i:03d}",
            task_id="task_1",
            mode="offline",
            search_mode="sequential",
            state="running",
            created_at=f"2026-10-18T00:{i // 60:02d}:{i % 60:02d}Z",
        )

    # Insert matching running run at position 106
    test_repo.create_run(
        run_id="run_k3_accept_interrupted_hidden",
        task_id="task_1",
        mode="offline",
        search_mode="sequential",
        state="running",
        created_at="2026-10-18T02:00:00Z",
    )

    recover_interrupted_runs(test_repo, acceptance_prefix="run_k3_accept_")

    target_run = test_repo.get_run("run_k3_accept_interrupted_hidden")
    assert target_run.state == "failed"

    # Verify unrelated runs remain in running state
    assert test_repo.get_run("run_unrelated_running_000").state == "running"
    assert test_repo.get_run("run_unrelated_running_104").state == "running"


@pytest.mark.asyncio
async def test_queue_worker_no_matching_runs_returns_false(test_repo: D1StorageRepository) -> None:
    """When no queued runs match acceptance_prefix, worker returns False and skips processing."""
    test_repo.upsert_task({
        "task_id": "task_1",
        "title": "Test task",
        "repository_url": "https://github.com/example/repo",
        "commit_sha": "abc123",
        "dependency": "pkg",
        "from_version": "1.0",
        "to_version": "2.0",
    })

    test_repo.create_run(
        run_id="run_unrelated_only",
        task_id="task_1",
        mode="offline",
        search_mode="sequential",
        state="queued",
    )

    worker = QueueWorker(
        repo=test_repo,
        acceptance_prefix="run_k3_accept_",
    )

    processed = await worker.process_one()
    assert processed is False

    # Unrelated run remains queued
    run = test_repo.get_run("run_unrelated_only")
    assert run.state == "queued"


def test_create_run_respects_configured_prefix(test_repo: D1StorageRepository) -> None:
    """POST /api/runs generates run_id with acceptance prefix when configured."""
    test_repo.upsert_task({
        "task_id": "task_1",
        "title": "Test task",
        "repository_url": "https://github.com/example/repo",
        "commit_sha": "abc123",
        "dependency": "pkg",
        "from_version": "1.0",
        "to_version": "2.0",
    })

    app = create_app(repository=test_repo)
    with patch("src.main.settings.repomedic_acceptance_prefix", "run_k3_accept_"):
        client = TestClient(app)
        res = client.post("/api/runs", json={"task_id": "task_1", "search_mode": "sequential"})
        assert res.status_code == 202
        data = res.json()
        assert data["run_id"].startswith("run_k3_accept_")


def test_create_run_default_prefix(test_repo: D1StorageRepository) -> None:
    """POST /api/runs generates default run_ prefix when acceptance prefix is empty."""
    test_repo.upsert_task({
        "task_id": "task_1",
        "title": "Test task",
        "repository_url": "https://github.com/example/repo",
        "commit_sha": "abc123",
        "dependency": "pkg",
        "from_version": "1.0",
        "to_version": "2.0",
    })

    app = create_app(repository=test_repo)
    with patch("src.main.settings.repomedic_acceptance_prefix", ""):
        client = TestClient(app)
        res = client.post("/api/runs", json={"task_id": "task_1", "search_mode": "sequential"})
        assert res.status_code == 202
        data = res.json()
        assert data["run_id"].startswith("run_")
        assert not data["run_id"].startswith("run_k3_accept_")
