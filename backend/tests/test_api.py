import pytest
from fastapi.testclient import TestClient
import httpx

from src.main import create_app
from src.storage.db_client import RepoMedicDB
from src.storage.repository import D1StorageRepository
from tests.test_storage import create_sqlite_d1_transport


@pytest.fixture
def test_app_and_repo():
    transport = create_sqlite_d1_transport(expected_token="test-bridge-token")
    mock_db = RepoMedicDB(
        base_url="http://test-bridge",
        api_key="test-bridge-token",
        transport=transport,
    )
    repo = D1StorageRepository(mock_db)
    app = create_app(repository=repo)
    return app, repo


def test_startup_lifespan_task_sync(test_app_and_repo):
    """Test that task fixtures from fixtures/tasks are synced on startup (AC-1)."""
    app, repo = test_app_and_repo
    with TestClient(app) as client:
        response = client.get("/api/tasks")
        assert response.status_code == 200
        data = response.json()
        assert "tasks" in data
        assert len(data["tasks"]) >= 1
        task_ids = [t["task_id"] for t in data["tasks"]]
        assert "example-task-1" in task_ids


def test_get_tasks_empty_and_populated(test_app_and_repo):
    """Verify AC-1: GET /api/tasks returns 200 with TaskSummary array."""
    app, repo = test_app_and_repo
    # Pre-populate a custom task
    repo.upsert_task({
        "task_id": "custom-task-42",
        "title": "Upgrade requests to 2.32",
        "repository_url": "https://github.com/test/repo",
        "commit_sha": "1234567890ab",
        "dependency": "requests",
        "from_version": "2.28.0",
        "to_version": "2.32.0",
    })

    client = TestClient(app)
    response = client.get("/api/tasks")
    assert response.status_code == 200
    tasks = response.json()["tasks"]
    custom = [t for t in tasks if t["task_id"] == "custom-task-42"]
    assert len(custom) == 1
    assert custom[0]["dependency"] == "requests"


def test_post_runs_happy_path(test_app_and_repo):
    """Verify AC-2: POST /api/runs creates queued run, returns 202 with RunSummary."""
    app, repo = test_app_and_repo
    repo.upsert_task({
        "task_id": "task-test-run",
        "title": "Test task",
        "repository_url": "https://github.com/test/repo",
        "commit_sha": "123456",
        "dependency": "click",
        "from_version": "8.0",
        "to_version": "8.1",
    })

    client = TestClient(app)
    payload = {
        "task_id": "task-test-run",
        "search_mode": "sequential",
    }
    response = client.post("/api/runs", json=payload)
    assert response.status_code == 202
    data = response.json()
    assert data["run_id"].startswith("run_")
    assert data["task_id"] == "task-test-run"
    assert data["state"] == "queued"
    assert data["search_mode"] == "sequential"
    assert data["mode"] == "offline"
    assert "usage" in data
    assert data["usage"]["model_calls"] == 0
    assert data["artifacts"] == []

    # Verify run is actually in D1
    persisted = repo.get_run(data["run_id"])
    assert persisted.run_id == data["run_id"]
    assert persisted.state == "queued"


def test_post_runs_missing_or_unknown_task(test_app_and_repo):
    """Verify AC-3: POST /api/runs rejects unknown task with 404 code not_found."""
    app, _ = test_app_and_repo
    client = TestClient(app)

    response = client.post("/api/runs", json={"task_id": "non-existent-task", "search_mode": "sequential"})
    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "not_found"
    assert "non-existent-task" in error["message"]


def test_post_runs_invalid_body_and_extra_fields(test_app_and_repo):
    """Verify AC-3: POST /api/runs rejects unknown fields or invalid search_mode with 422 invalid_request."""
    app, repo = test_app_and_repo
    repo.upsert_task({
        "task_id": "task-valid",
        "title": "Valid task",
        "repository_url": "https://github.com/test/repo",
        "commit_sha": "123456",
        "dependency": "pkg",
        "from_version": "1.0",
        "to_version": "2.0",
    })
    client = TestClient(app)

    # Unknown field forbidden
    resp_extra = client.post("/api/runs", json={
        "task_id": "task-valid",
        "search_mode": "sequential",
        "unexpected_field": "dangerous",
    })
    assert resp_extra.status_code == 422
    assert resp_extra.json()["error"]["code"] == "invalid_request"

    # Invalid search mode literal
    resp_invalid_mode = client.post("/api/runs", json={
        "task_id": "task-valid",
        "search_mode": "magic_mode",
    })
    assert resp_invalid_mode.status_code == 422
    assert resp_invalid_mode.json()["error"]["code"] == "invalid_request"


def test_get_run_by_id(test_app_and_repo):
    """Verify AC-4: GET /api/runs/{id} returns 200 for existing run, 404 for missing run."""
    app, repo = test_app_and_repo
    repo.upsert_task({
        "task_id": "task-get-run",
        "title": "Task for get run",
        "repository_url": "https://github.com/test/repo",
        "commit_sha": "123456",
        "dependency": "pkg",
        "from_version": "1.0",
        "to_version": "2.0",
    })
    created = repo.create_run("run_specific_123", "task-get-run", "offline", "sequential", max_run_usd=2.0)

    client = TestClient(app)

    # 1. Existing run
    resp = client.get(f"/api/runs/{created.run_id}")
    assert resp.status_code == 200
    assert resp.json()["run_id"] == "run_specific_123"
    assert resp.json()["task_id"] == "task-get-run"

    # 2. Non-existent run
    resp_missing = client.get("/api/runs/run_does_not_exist")
    assert resp_missing.status_code == 404
    assert resp_missing.json()["error"]["code"] == "not_found"


def test_get_runs_history_and_filtering(test_app_and_repo):
    """Verify AC-5: GET /api/runs returns run summaries with limit and task_id filter."""
    app, repo = test_app_and_repo
    repo.create_run("run_h1", "task-1", "offline", "sequential")
    repo.create_run("run_h2", "task-2", "offline", "branch_refine")
    repo.create_run("run_h3", "task-1", "offline", "sequential")

    client = TestClient(app)

    # 1. Fetch all
    resp = client.get("/api/runs")
    assert resp.status_code == 200
    runs = resp.json()["runs"]
    assert len(runs) == 3

    # 2. Limit parameter
    resp_limited = client.get("/api/runs?limit=2")
    assert resp_limited.status_code == 200
    assert len(resp_limited.json()["runs"]) == 2

    # 3. Task filter
    resp_filtered = client.get("/api/runs?task_id=task-2")
    assert resp_filtered.status_code == 200
    assert len(resp_filtered.json()["runs"]) == 1
    assert resp_filtered.json()["runs"][0]["run_id"] == "run_h2"

    # 4. Limit validation out of range (ge=1, le=100)
    resp_invalid_limit = client.get("/api/runs?limit=0")
    assert resp_invalid_limit.status_code == 422
    assert resp_invalid_limit.json()["error"]["code"] == "invalid_request"

    resp_excessive_limit = client.get("/api/runs?limit=105")
    assert resp_excessive_limit.status_code == 422
    assert resp_excessive_limit.json()["error"]["code"] == "invalid_request"

    # 5. State filter validation
    resp_invalid_state = client.get("/api/runs?state=bogus")
    assert resp_invalid_state.status_code == 422
    assert resp_invalid_state.json()["error"]["code"] == "invalid_request"


def test_database_bridge_unavailable_503():
    """Verify AC-6: When D1 database worker fails or times out, returns 503 unavailable."""
    def broken_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused by mock bridge")

    failing_transport = httpx.MockTransport(broken_handler)
    failing_db = RepoMedicDB(
        base_url="http://unreachable-bridge",
        api_key="token",
        transport=failing_transport,
    )
    repo = D1StorageRepository(failing_db)
    app = create_app(repository=repo)
    client = TestClient(app)

    # Calling /api/tasks when bridge is down returns 503
    resp = client.get("/api/tasks")
    assert resp.status_code == 503
    error = resp.json()["error"]
    assert error["code"] == "unavailable"
    assert "Database bridge unavailable" in error["message"]


def test_cors_headers_present(test_app_and_repo):
    """Verify CORS middleware is active for local development frontend origin."""
    app, _ = test_app_and_repo
    client = TestClient(app)
    response = client.get(
        "/api/tasks",
        headers={"Origin": "http://localhost:3000"},
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
