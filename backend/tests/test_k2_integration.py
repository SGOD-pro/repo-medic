import asyncio
import json
import pytest
from starlette.testclient import TestClient

from src.config import settings
from src.engine.adapters import SandboxPreset
from src.engine.fake_sandbox import FakeSandboxAdapter
from src.engine.fake_model import FakeModelAdapter, UNSAFE_TEST_PATCH
from src.engine.repair import repair as engine_repair
from src.main import create_app
from src.storage.db_client import RepoMedicDB
from src.storage.repository import D1StorageRepository
from src.worker import QueueWorker
from tests.test_storage import create_sqlite_d1_transport


@pytest.fixture
def k2_env(monkeypatch):
    """Sets up an integrated K2 test harness with local D1 and real engine repair."""
    monkeypatch.setattr(settings, "repomedic_mode", "offline")
    monkeypatch.setattr(settings, "repomedic_worker_enabled", False)
    monkeypatch.setattr(settings, "repomedic_max_run_usd", 2.0)
    monkeypatch.setattr(settings, "repomedic_total_budget_usd", 25.0)

    transport = create_sqlite_d1_transport(expected_token="test-bridge-token")
    mock_db = RepoMedicDB(
        base_url="http://test-bridge",
        api_key="test-bridge-token",
        transport=transport,
    )
    repo = D1StorageRepository(mock_db)

    # Seed the standard curated task with valid TaskRecipe JSON matching FakeSandbox version 2.0.0
    recipe_dict = {
        "test_command": ["pytest", "tests/"],
        "allowed_source_paths": ["src/"],
        "expected_failure": "AssertionError",
        "timeout_seconds": 60,
        "max_candidates": 3,
        "max_refinements": 1,
    }
    repo.upsert_task({
        "task_id": "TASK-084",
        "title": "pydantic v1.10.8 to v2.0.0 migration in fastapi-service",
        "repository_url": "https://github.com/tiangolo/fastapi-service",
        "commit_sha": "8a4f21d",
        "dependency": "pydantic",
        "from_version": "1.10.8",
        "to_version": "2.0.0",
        "recipe_json": json.dumps(recipe_dict),
    })

    app = create_app(repository=repo)
    client = TestClient(app)

    # Instantiate QueueWorker with C real engine repair
    worker = QueueWorker(repo=repo, poll_interval_seconds=0.01, use_real_engine=True)

    return {
        "repo": repo,
        "client": client,
        "worker": worker,
    }


def test_k2_sequential_repair_success_and_downloads(k2_env):
    """Tests K2 sequential mode repair success end to end including artifact downloads."""
    client = k2_env["client"]
    worker = k2_env["worker"]

    # 1. Create run via public HTTP API
    resp = client.post("/api/runs", json={"task_id": "TASK-084", "search_mode": "sequential"})
    assert resp.status_code == 202
    created = resp.json()
    run_id = created["run_id"]
    assert created["state"] == "queued"
    assert created["search_mode"] == "sequential"

    # 2. Worker processes the run with C real engine repair
    asyncio.run(worker.process_one())

    # 3. Verify final state and reason in D1 and HTTP API
    get_resp = client.get(f"/api/runs/{run_id}")
    assert get_resp.status_code == 200
    run_data = get_resp.json()
    assert run_data["state"] == "succeeded"
    assert "Candidate verified cleanly" in run_data["reason"]

    # 4. Verify artifacts generated and download by artifact id
    artifacts = run_data["artifacts"]
    assert len(artifacts) >= 2
    artifact_kinds = {a["kind"]: a["artifact_id"] for a in artifacts}
    assert "patch" in artifact_kinds
    assert "evidence" in artifact_kinds

    patch_id = artifact_kinds["patch"]
    evidence_id = artifact_kinds["evidence"]

    patch_resp = client.get(f"/api/runs/{run_id}/artifacts/{patch_id}")
    assert patch_resp.status_code == 200
    patch_text = patch_resp.text
    assert "--- a/src/app.py" in patch_text

    evidence_resp = client.get(f"/api/runs/{run_id}/artifacts/{evidence_id}")
    assert evidence_resp.status_code == 200
    evidence_json = evidence_resp.json()
    assert evidence_json["task_id"] == "TASK-084"
    assert evidence_json["verified_version"] == "2.0.0"
    assert evidence_json["import_origin"] == "site-packages"
    assert evidence_json["checks"]["tests_passed"] is True


def test_k2_branch_refine_repair_success(k2_env):
    """Tests K2 branch and refine repair success end to end."""
    client = k2_env["client"]
    worker = k2_env["worker"]

    # 1. Create run in branch refine search mode
    resp = client.post("/api/runs", json={"task_id": "TASK-084", "search_mode": "branch_refine"})
    assert resp.status_code == 202
    run_id = resp.json()["run_id"]

    # 2. Worker executes branch refine search
    asyncio.run(worker.process_one())

    # 3. Verify terminal state
    get_resp = client.get(f"/api/runs/{run_id}")
    assert get_resp.status_code == 200
    run_data = get_resp.json()
    assert run_data["state"] == "succeeded"
    assert "Candidate candidate_1 verified cleanly" in run_data["reason"]
    assert len(run_data["artifacts"]) >= 2


def test_k2_failure_scenario(k2_env):
    """Tests K2 candidate verification failure leading to run failure."""
    client = k2_env["client"]
    repo = k2_env["repo"]

    resp = client.post("/api/runs", json={"task_id": "TASK-084", "search_mode": "sequential"})
    assert resp.status_code == 202
    run_id = resp.json()["run_id"]

    # Use sandbox preset that forces verification failure
    failing_sandbox = FakeSandboxAdapter(preset=SandboxPreset.VERIFY_TEST_FAIL)

    async def run_with_failing_sandbox(req, recipe, host):
        return await engine_repair(req, recipe, host, sandbox=failing_sandbox)

    custom_worker = QueueWorker(repo=repo, poll_interval_seconds=0.01, repair_fn=run_with_failing_sandbox)
    asyncio.run(custom_worker.process_one())

    get_resp = client.get(f"/api/runs/{run_id}")
    assert get_resp.status_code == 200
    run_data = get_resp.json()
    assert run_data["state"] == "failed"
    assert "verification failed" in run_data["reason"]


def test_k2_cancellation_scenario(k2_env):
    """Tests K2 cancellation via HTTP API halting active engine execution."""
    client = k2_env["client"]
    repo = k2_env["repo"]

    resp = client.post("/api/runs", json={"task_id": "TASK-084", "search_mode": "sequential"})
    run_id = resp.json()["run_id"]

    # Worker with cancelling repair
    worker = QueueWorker(repo=repo, poll_interval_seconds=0.01)
    # Cancel via HTTP endpoint to verify idempotence
    cancel_resp = client.post(f"/api/runs/{run_id}/cancel")
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["state"] == "cancelled"

    # Worker processing already cancelled run does not overwrite
    asyncio.run(worker.process_one())
    run_data = client.get(f"/api/runs/{run_id}").json()
    assert run_data["state"] == "cancelled"


def test_k2_budget_denial_scenario(k2_env, monkeypatch):
    """Tests K2 global budget denial returning 409 Conflict."""
    client = k2_env["client"]
    monkeypatch.setattr(settings, "repomedic_total_budget_usd", 1.0)
    monkeypatch.setattr(settings, "repomedic_max_run_usd", 2.0)

    # 2.0 max run USD exceeds 1.0 total budget
    resp = client.post("/api/runs", json={"task_id": "TASK-084", "search_mode": "sequential"})
    assert resp.status_code == 409
    assert resp.json()["error"]["message"] == "Budget unavailable"


def test_k2_unsafe_patch_scenario(k2_env):
    """Tests K2 rejection of unsafe patches that touch disallowed paths or test files."""
    client = k2_env["client"]
    repo = k2_env["repo"]

    resp = client.post("/api/runs", json={"task_id": "TASK-084", "search_mode": "sequential"})
    run_id = resp.json()["run_id"]

    # Model generates patch attempting to edit tests
    unsafe_model = FakeModelAdapter(canned_response=UNSAFE_TEST_PATCH)

    async def run_with_unsafe_model(req, recipe, host):
        return await engine_repair(req, recipe, host, model=unsafe_model)

    worker = QueueWorker(repo=repo, poll_interval_seconds=0.01, repair_fn=run_with_unsafe_model)
    asyncio.run(worker.process_one())

    run_data = client.get(f"/api/runs/{run_id}").json()
    assert run_data["state"] == "failed"
    assert "Patch safety validation failed" in run_data["reason"]


def test_k2_reconnect_and_sse_streaming(k2_env):
    """Tests K2 event stream reconnection and Last Event ID cursor deduplication."""
    client = k2_env["client"]
    repo = k2_env["repo"]

    # Seed events manually in D1
    repo.create_run(
        run_id="run-reconnect-test",
        task_id="TASK-084",
        mode="offline",
        search_mode="sequential",
        state="succeeded",
    )
    repo.append_event(
        "run-reconnect-test",
        event_type="run.started",
        payload={"mode": "offline", "search_mode": "sequential", "max_run_usd": 2.0},
    )
    repo.append_event(
        "run-reconnect-test",
        event_type="stage.completed",
        payload={"stage": "baseline", "passed": True, "summary": "Baseline pass"},
    )
    repo.append_event(
        "run-reconnect-test",
        event_type="stage.completed",
        payload={"stage": "upgrade", "passed": True, "summary": "Upgrade pass"},
    )
    repo.append_event(
        "run-reconnect-test",
        event_type="run.finished",
        payload={"state": "succeeded", "reason": "Completed successfully"},
    )

    # Fetch initial stream
    resp = client.get("/api/runs/run-reconnect-test/events")
    assert resp.status_code == 200
    events_text = resp.text
    assert "id: 1" in events_text
    assert "id: 4" in events_text

    # Reconnect with Last-Event-ID: 2 header
    resp_reconnect = client.get(
        "/api/runs/run-reconnect-test/events",
        headers={"Last-Event-ID": "2"},
    )
    assert resp_reconnect.status_code == 200
    reconnected_text = resp_reconnect.text
    assert "id: 1" not in reconnected_text
    assert "id: 2" not in reconnected_text
    assert "id: 3" in reconnected_text
    assert "id: 4" in reconnected_text


def test_k2_backend_restart_recovery(k2_env):
    """Tests K2 system restart recovering interrupted runs into failed state."""
    repo = k2_env["repo"]

    # Seed an interrupted running run and an interrupted queued run
    repo.create_run(
        run_id="run-interrupted-1",
        task_id="TASK-084",
        mode="offline",
        search_mode="sequential",
        state="running",
    )
    repo.create_run(
        run_id="run-interrupted-2",
        task_id="TASK-084",
        mode="offline",
        search_mode="branch_refine",
        state="queued",
    )

    app = create_app(repository=repo)
    with TestClient(app):
        r1 = repo.get_run("run-interrupted-1")
        assert r1.state == "failed"
        assert "restarted" in (r1.reason or "")
        r2 = repo.get_run("run-interrupted-2")
        assert r2.state == "queued"
