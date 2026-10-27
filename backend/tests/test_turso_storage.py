import asyncio
import threading
import pytest

from src.storage.exceptions import (
    StorageConflictError,
    StorageError,
    StorageLimitExceededError,
    StorageNotFoundError,
)
from src.storage.repository import TursoHostPorts, TursoStorageRepository
from src.storage.turso_client import TursoClient


@pytest.fixture
def turso_client(tmp_path):
    db_file = str(tmp_path / "test_turso.db")
    client = TursoClient(database=db_file)
    yield client
    client.close()


@pytest.fixture
def turso_repo(turso_client):
    return TursoStorageRepository(client=turso_client)


def test_turso_health(turso_client):
    res = turso_client.health()
    assert res["ok"] is True
    assert res["engine"] == "libsql"
    assert res["status"] == "healthy"


def test_turso_task_crud(turso_repo):
    task_data = {
        "task_id": "TASK-TURSO-1",
        "title": "Migrate to Turso",
        "repository_url": "https://github.com/example/repo.git",
        "commit_sha": "abc1234",
        "dependency": "libsql",
        "from_version": "0.1.0",
        "to_version": "0.2.0",
        "test_command": ["pytest"],
    }
    turso_repo.upsert_task(task_data)

    task = turso_repo.get_task("TASK-TURSO-1")
    assert task is not None
    assert task.task_id == "TASK-TURSO-1"
    assert task.title == "Migrate to Turso"
    assert task.dependency == "libsql"

    tasks = turso_repo.list_tasks()
    assert any(t.task_id == "TASK-TURSO-1" for t in tasks)

    assert turso_repo.get_task("NONEXISTENT") is None


def test_turso_run_lifecycle_and_cas(turso_repo):
    task_data = {
        "task_id": "TASK-TURSO-2",
        "title": "Run test task",
        "repository_url": "https://github.com/example/repo.git",
        "commit_sha": "1234567",
        "dependency": "pkg",
        "from_version": "1.0",
        "to_version": "2.0",
    }
    turso_repo.upsert_task(task_data)

    run = turso_repo.create_run(
        run_id="run_turso_1",
        task_id="TASK-TURSO-2",
        mode="offline",
        search_mode="sequential",
        max_run_usd=2.0,
        state="queued",
    )
    assert run.run_id == "run_turso_1"
    assert run.state == "queued"

    with pytest.raises(StorageConflictError):
        turso_repo.create_run(
            run_id="run_turso_1",
            task_id="TASK-TURSO-2",
            mode="offline",
            search_mode="sequential",
        )

    turso_repo.update_run_state("run_turso_1", state="running", from_state="queued")
    fetched = turso_repo.get_run("run_turso_1")
    assert fetched.state == "running"

    with pytest.raises(StorageConflictError):
        turso_repo.update_run_state("run_turso_1", state="succeeded", from_state="queued")

    turso_repo.finish_run("run_turso_1", state="succeeded", reason="Verification clean")
    terminal_run = turso_repo.get_run("run_turso_1")
    assert terminal_run.state == "succeeded"
    assert terminal_run.reason == "Verification clean"

    with pytest.raises(StorageConflictError):
        turso_repo.update_run_state("run_turso_1", state="failed")


def test_turso_ordered_events(turso_repo):
    turso_repo.create_run(
        run_id="run_events_1",
        task_id="TASK-TURSO-1",
        mode="offline",
        search_mode="sequential",
    )

    ev1 = turso_repo.append_event(
        "run_events_1",
        "run.started",
        {"task_id": "TASK-TURSO-1", "mode": "offline", "search_mode": "sequential", "max_run_usd": 2.0},
    )
    assert ev1.seq == 1
    assert ev1.type == "run.started"

    ev2 = turso_repo.append_event(
        "run_events_1",
        "stage.completed",
        {"stage": "baseline", "passed": True, "summary": "clean"},
    )
    assert ev2.seq == 2

    ev3 = turso_repo.append_event(
        "run_events_1",
        "usage.updated",
        {"model_calls": 1, "input_tokens": 100, "output_tokens": 50, "estimated_usd": 0.05},
    )
    assert ev3.seq == 3

    events_all = turso_repo.list_events("run_events_1", after=0)
    assert len(events_all) == 3
    assert [e.seq for e in events_all] == [1, 2, 3]

    events_after_1 = turso_repo.list_events("run_events_1", after=1)
    assert len(events_after_1) == 2
    assert [e.seq for e in events_after_1] == [2, 3]

    run = turso_repo.get_run("run_events_1")
    assert run.usage.model_calls == 1
    assert run.usage.estimated_usd == 0.05


def test_turso_artifacts_limits(turso_repo):
    turso_repo.create_run(
        run_id="run_art_1",
        task_id="TASK-TURSO-1",
        mode="offline",
        search_mode="sequential",
    )

    patch_bytes = b"diff --git a/test.py b/test.py\n+hello"
    art = turso_repo.store_artifact("run_art_1", kind="patch", filename="patch.diff", content=patch_bytes)
    assert art.artifact_id.startswith("art_")
    assert art.kind == "patch"

    read_back = turso_repo.get_artifact_content("run_art_1", art.artifact_id)
    assert read_back == patch_bytes

    oversized = b"x" * (1048576 + 1)
    with pytest.raises(StorageLimitExceededError):
        turso_repo.store_artifact("run_art_1", kind="log", filename="large.log", content=oversized)


def test_turso_budget_atomic_reservations(turso_client):
    turso_client.create_run(
        run_id="run_budget_1",
        task_id="TASK-TURSO-1",
        mode="offline",
        search_mode="sequential",
        max_run_usd=1.0,
    )

    turso_client.reserve_budget("run_budget_1", "op_1", "model", 0.40, global_budget_usd=5.0)
    turso_client.reserve_budget("run_budget_1", "op_2", "sandbox", 0.50, global_budget_usd=5.0)

    with pytest.raises(StorageConflictError):
        turso_client.reserve_budget("run_budget_1", "op_3", "model", 0.20, global_budget_usd=5.0)

    turso_client.settle_budget("op_1", 0.35)

    usage = turso_client.get_budget_usage()
    assert usage["settled_micro_usd"] == 350000
    assert usage["reserved_micro_usd"] == 500000
    assert usage["total_micro_usd"] == 850000

    turso_client.settle_budget("op_1", 0.35)

    with pytest.raises(StorageConflictError):
        turso_client.settle_budget("op_1", 0.40)


def test_turso_concurrent_budget_reservations(turso_client):
    turso_client.create_run(
        run_id="run_concurrent_1",
        task_id="TASK-TURSO-1",
        mode="offline",
        search_mode="branch_refine",
        max_run_usd=1.0,
    )

    successes = []
    failures = []

    def try_reserve(idx):
        try:
            turso_client.reserve_budget(
                "run_concurrent_1",
                f"op_conc_{idx}",
                "model",
                0.20,
                global_budget_usd=10.0,
            )
            successes.append(idx)
        except StorageConflictError:
            failures.append(idx)

    threads = [threading.Thread(target=try_reserve, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(successes) == 5
    assert len(failures) == 5


@pytest.mark.asyncio
async def test_turso_host_ports_lifecycle(turso_repo):
    turso_repo.create_run(
        run_id="run_hp_1",
        task_id="TASK-TURSO-1",
        mode="offline",
        search_mode="sequential",
        max_run_usd=2.0,
    )
    hp = TursoHostPorts(run_id="run_hp_1", repo=turso_repo)

    await hp.emit("stage.completed", {"stage": "upgrade", "passed": True, "summary": "Upgrade clean"})
    events = turso_repo.list_events("run_hp_1")
    assert len(events) == 1
    assert events[0].type == "stage.completed"

    reserved = await hp.reserve("model:1", 0.05)
    assert reserved is True

    reserved_huge = await hp.reserve("model:huge", 9999.0)
    assert reserved_huge is False

    await hp.settle("model:1", 0.04)
    usage = hp.client.get_budget_usage()
    assert usage["settled_micro_usd"] == 40000

    art_id = await hp.save_artifact("patch", "patch.diff", b"dummy patch")
    assert art_id.startswith("art_")

    assert await hp.cancelled() is False
    turso_repo.update_run_state("run_hp_1", state="cancelled")
    assert await hp.cancelled() is True


def test_turso_exact_manifest_cleanup(turso_client):
    turso_client.upsert_task({
        "task_id": "TASK-CLEANUP-1",
        "title": "Cleanup task",
        "repository_url": "https://github.com/example/repo.git",
        "commit_sha": "clean123",
        "dependency": "pkg",
        "from_version": "1.0",
        "to_version": "2.0",
    })
    turso_client.create_run("run_clean_1", "TASK-CLEANUP-1", "offline", "sequential")
    turso_client.create_event("run_clean_1", "stage.completed", {"stage": "baseline"})
    turso_client.store_artifact("run_clean_1", "art_clean_1", "patch", "p.diff", "sha", 10, "b64==")
    turso_client.reserve_budget("run_clean_1", "op_clean_1", "model", 0.10)

    manifest = {
        "tasks": ["TASK-CLEANUP-1"],
        "runs": ["run_clean_1"],
        "operations": ["op_clean_1"],
        "artifacts": ["art_clean_1"],
    }

    res = turso_client.cleanup_manifest(manifest)
    assert res["deleted"]["tasks"] == 1
    assert res["deleted"]["runs"] == 1
    assert res["deleted"]["operations"] == 1
    assert res["deleted"]["artifacts"] == 1
    assert res["deleted"]["events"] == 1

    with pytest.raises(StorageNotFoundError):
        turso_client.get_run("run_clean_1")


def test_turso_concurrent_conflicting_settlement_cannot_overwrite(turso_client):
    """Prove that concurrent conflicting settlements cannot overwrite each other."""
    turso_client.upsert_task({
        "task_id": "TASK-TURSO-RACE",
        "title": "Race task",
        "repository_url": "https://github.com/example/repo.git",
        "commit_sha": "abc1234",
        "dependency": "pkg",
        "from_version": "1.0",
        "to_version": "2.0",
    })
    turso_client.create_run(
        run_id="run_settle_race",
        task_id="TASK-TURSO-RACE",
        mode="offline",
        search_mode="sequential",
        max_run_usd=2.0,
    )
    turso_client.reserve_budget("run_settle_race", "op_race_1", "model", 0.50, global_budget_usd=10.0)

    # 1. Race two conflicting amounts: $0.05 vs $0.10
    amounts = [0.05, 0.10]
    results = {}
    errors = {}

    def settle_worker(amt: float):
        try:
            res = turso_client.settle_budget("op_race_1", amt)
            results[amt] = res
        except Exception as exc:
            errors[amt] = exc

    t1 = threading.Thread(target=settle_worker, args=(amounts[0],))
    t2 = threading.Thread(target=settle_worker, args=(amounts[1],))

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Exactly one amount won and the other was rejected with conflict
    assert len(results) == 1
    assert len(errors) == 1
    losing_amt = amounts[1] if amounts[0] in results else amounts[0]
    winning_amt = amounts[0] if amounts[0] in results else amounts[1]

    assert isinstance(errors[losing_amt], StorageConflictError)
    assert errors[losing_amt].code == "operation_already_settled"

    # Verify database strictly preserved the winner's amount and did not overwrite
    cur = turso_client._conn.execute(
        "SELECT settled_micro_usd, status FROM operations WHERE operation_id = ?",
        ("op_race_1",),
    )
    row = cur.fetchone()
    assert row[1] == "settled"
    assert row[0] == int(winning_amt * 1_000_000)

    # 2. Idempotent retry with winning amount succeeds
    retry_res = turso_client.settle_budget("op_race_1", winning_amt)
    assert retry_res["ok"] is True

    # 3. Conflicting retry with losing amount still fails
    with pytest.raises(StorageConflictError) as exc_info:
        turso_client.settle_budget("op_race_1", losing_amt)
    assert exc_info.value.code == "operation_already_settled"


def test_operation_endpoint_disabled_in_production(turso_repo, monkeypatch):
    """Verify internal operation reservation endpoint is disabled in production."""
    from fastapi.testclient import TestClient
    from src.main import create_app

    turso_repo.create_run(
        run_id="run_op_prod",
        task_id="TASK-TURSO-1",
        mode="offline",
        search_mode="sequential",
        max_run_usd=2.0,
    )

    app = create_app(repository=turso_repo)
    client = TestClient(app)

    # 1. In production mode, endpoint must return 404
    monkeypatch.setenv("REPOMEDIC_ENV", "production")
    resp_prod = client.post(
        "/api/runs/run_op_prod/operations",
        json={"operation_id": "op_test_prod", "kind": "model", "reserved_micro_usd": 50000},
    )
    assert resp_prod.status_code == 404
    error_msg = resp_prod.json().get("error", {}).get("message", "") or resp_prod.json().get("detail", "")
    assert "disabled in production" in error_msg

    # 2. In development mode, endpoint works and enforces server budget
    monkeypatch.setenv("REPOMEDIC_ENV", "development")
    resp_dev = client.post(
        "/api/runs/run_op_prod/operations",
        json={"operation_id": "op_test_dev", "kind": "model", "reserved_micro_usd": 50000},
    )
    assert resp_dev.status_code == 201
    assert resp_dev.json().get("ok") is True
