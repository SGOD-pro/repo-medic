import pytest
from fastapi.testclient import TestClient

from src.contracts import CustomRepositoryConfig, SUPPORTED_DEMO_TASK_IDS
from src.custom_validation import validate_custom_config
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


def sample_valid_config() -> CustomRepositoryConfig:
    return CustomRepositoryConfig(
        repository_url="https://github.com/SGOD-pro/repo-medic.git",
        commit_sha="8c400721558392a23b3af71766f673da02f80040",
        dependency="sqlalchemy",
        from_version="1.4.48",
        to_version="2.0.19",
        pytest_args=["pytest", "tests/"],
        allowed_source_paths=["src/shop/database.py", "src/shop/models.py"],
        expected_failure="AttributeError: 'Engine' object has no attribute 'execute'",
    )


def test_validate_custom_config_valid():
    config = sample_valid_config()
    result = validate_custom_config(config)
    assert result.valid is True
    assert len(result.errors) == 0
    assert result.custom_execution_supported is False
    assert result.gate_status == "disabled"
    assert "disabled" in result.gate_message.lower()


def test_validate_custom_config_invalid_url():
    config = sample_valid_config()
    config.repository_url = "http://insecure.example.com/repo"
    result = validate_custom_config(config)
    assert result.valid is False
    assert "repository_url" in result.field_errors
    assert any("public GitHub HTTPS URL" in err for err in result.field_errors["repository_url"])


def test_validate_custom_config_short_commit_sha():
    config = sample_valid_config()
    config.commit_sha = "8c40072"
    result = validate_custom_config(config)
    assert result.valid is False
    assert "commit_sha" in result.field_errors
    assert any("40 character hexadecimal" in err for err in result.field_errors["commit_sha"])


def test_validate_custom_config_same_versions():
    config = sample_valid_config()
    config.to_version = config.from_version
    result = validate_custom_config(config)
    assert result.valid is False
    assert "to_version" in result.field_errors
    assert any("differ from baseline" in err for err in result.field_errors["to_version"])


def test_validate_custom_config_dangerous_pytest_args():
    config = sample_valid_config()
    config.pytest_args = ["tests/", "; rm -rf /"]
    result = validate_custom_config(config)
    assert result.valid is False
    assert "pytest_args" in result.field_errors
    assert any("shell operators" in err for err in result.field_errors["pytest_args"])


def test_validate_custom_config_path_traversal():
    config = sample_valid_config()
    config.allowed_source_paths = ["../etc/passwd", "src/valid.py"]
    result = validate_custom_config(config)
    assert result.valid is False
    assert "allowed_source_paths" in result.field_errors
    assert any("directory traversal" in err for err in result.field_errors["allowed_source_paths"])


def test_api_custom_validate_endpoint(test_app_and_repo):
    app, repo = test_app_and_repo
    client = TestClient(app)

    valid_payload = sample_valid_config().model_dump()
    response = client.post("/api/custom/validate", json=valid_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["gate_status"] == "disabled"
    assert data["custom_execution_supported"] is False


def test_api_custom_execute_and_run_forbidden(test_app_and_repo):
    app, repo = test_app_and_repo
    client = TestClient(app)

    # Calling execute directly must return 403 Forbidden
    resp1 = client.post("/api/custom/execute")
    assert resp1.status_code == 403
    data1 = resp1.json()
    assert data1["error"]["code"] == "custom_execution_disabled"

    # Calling run directly must return 403 Forbidden
    resp2 = client.post("/api/custom/run")
    assert resp2.status_code == 403
    data2 = resp2.json()
    assert data2["error"]["code"] == "custom_execution_disabled"


def test_api_runs_rejects_custom_task_bypass(test_app_and_repo):
    app, repo = test_app_and_repo
    client = TestClient(app)

    # Attempting to start a run with custom task identifier must be rejected with 403 Forbidden
    resp = client.post(
        "/api/runs",
        json={
            "task_id": "custom-task-untrusted",
            "search_mode": "sequential",
        },
    )
    assert resp.status_code == 403
    data = resp.json()
    assert "custom repository execution is disabled" in data["error"]["message"].lower()

    # Also test task-custom prefix
    resp2 = client.post(
        "/api/runs",
        json={
            "task_id": "task-custom-untrusted",
            "search_mode": "sequential",
        },
    )
    assert resp2.status_code == 403


def test_api_runs_policy_approved_demos(test_app_and_repo):
    app, repo = test_app_and_repo
    # Seed approved demo tasks
    repo.upsert_task({
        "task_id": "TASK-DEMO-SHOP",
        "title": "demo shop",
        "repository_url": "https://github.com/SGOD-pro/repo-medic.git",
        "commit_sha": "8c400721558392a23b3af71766f673da02f80040",
        "dependency": "sqlalchemy",
        "from_version": "1.4.48",
        "to_version": "2.0.19",
    })
    repo.upsert_task({
        "task_id": "TASK-091",
        "title": "fixture task 091",
        "repository_url": "https://github.com/SGOD-pro/repo-medic.git",
        "commit_sha": "453a0b6c6b125177504cdd941902b8d48266ed1c",
        "dependency": "sqlalchemy",
        "from_version": "1.4.48",
        "to_version": "2.0.19",
    })

    client = TestClient(app)

    # Both approved demo tasks must be accepted with 202
    resp1 = client.post("/api/runs", json={"task_id": "TASK-DEMO-SHOP", "search_mode": "sequential"})
    assert resp1.status_code == 202
    data1 = resp1.json()
    assert data1["state"] == "queued"
    assert data1["task_id"] == "TASK-DEMO-SHOP"

    resp2 = client.post("/api/runs", json={"task_id": "TASK-091", "search_mode": "sequential"})
    assert resp2.status_code == 202
    data2 = resp2.json()
    assert data2["state"] == "queued"
    assert data2["task_id"] == "TASK-091"


def test_api_runs_policy_rejects_unknown_ids(test_app_and_repo):
    app, repo = test_app_and_repo
    client = TestClient(app)

    # Unknown task ID must return 404
    resp = client.post("/api/runs", json={"task_id": "nonexistent-task-999", "search_mode": "sequential"})
    assert resp.status_code == 404
    data = resp.json()
    assert "not found" in data["error"]["message"].lower()


def test_api_runs_policy_rejects_existing_non_demo_ids(test_app_and_repo):
    app, repo = test_app_and_repo
    # Seed existing non-demo tasks
    repo.upsert_task({
        "task_id": "TASK-084",
        "title": "pydantic task",
        "repository_url": "https://github.com/tiangolo/fastapi-service",
        "commit_sha": "8a4f21d",
        "dependency": "pydantic",
        "from_version": "1.10.8",
        "to_version": "2.0.0",
    })
    repo.upsert_task({
        "task_id": "example-task-1",
        "title": "example acceptance task",
        "repository_url": "https://github.com/example/repo",
        "commit_sha": "abcdef123456",
        "dependency": "pytest-mock",
        "from_version": "3.10.0",
        "to_version": "3.11.1",
    })

    client = TestClient(app)

    # Existing non-demo task must be rejected with 403 Forbidden under execution policy
    resp1 = client.post("/api/runs", json={"task_id": "TASK-084", "search_mode": "sequential"})
    assert resp1.status_code == 403
    data1 = resp1.json()
    assert "execution policy violation" in data1["error"]["message"].lower()
    assert "only supported demo tasks" in data1["error"]["message"].lower()

    resp2 = client.post("/api/runs", json={"task_id": "example-task-1", "search_mode": "sequential"})
    assert resp2.status_code == 403
    data2 = resp2.json()
    assert "execution policy violation" in data2["error"]["message"].lower()


def test_api_runs_preserves_existing_runs_and_artifacts(test_app_and_repo):
    app, repo = test_app_and_repo
    # Create an existing historical run and artifact
    run_id = "run_historical_preserved_123"
    repo.create_run(
        run_id=run_id,
        task_id="TASK-084",
        mode="live",
        search_mode="sequential",
        max_run_usd=2.0,
    )
    repo.finish_run(run_id=run_id, state="succeeded", reason="Historical verification completed")
    art = repo.store_artifact(
        run_id=run_id,
        kind="patch",
        filename="patch.diff",
        content=b"diff --git a/test b/test",
    )
    art_id = art.artifact_id

    client = TestClient(app)

    # 1. GET /api/runs must return the run in history
    list_resp = client.get("/api/runs")
    assert list_resp.status_code == 200
    runs = list_resp.json()["runs"]
    matching = [r for r in runs if r["run_id"] == run_id]
    assert len(matching) == 1
    assert matching[0]["state"] == "succeeded"

    # 2. GET /api/runs/{run_id} must return detail
    detail_resp = client.get(f"/api/runs/{run_id}")
    assert detail_resp.status_code == 200
    detail_data = detail_resp.json()
    assert detail_data["run_id"] == run_id
    assert detail_data["state"] == "succeeded"

    # 3. GET /api/runs/{run_id}/artifacts/{art_id} must return artifact content
    art_resp = client.get(f"/api/runs/{run_id}/artifacts/{art_id}")
    assert art_resp.status_code == 200
    assert art_resp.content == b"diff --git a/test b/test"


def test_api_tasks_supported_demo_policy(test_app_and_repo):
    app, repo = test_app_and_repo
    repo.upsert_task({
        "task_id": "TASK-DEMO-SHOP",
        "title": "demo shop",
        "repository_url": "https://github.com/SGOD-pro/repo-medic.git",
        "commit_sha": "8c400721558392a23b3af71766f673da02f80040",
        "dependency": "sqlalchemy",
        "from_version": "1.4.48",
        "to_version": "2.0.19",
    })
    repo.upsert_task({
        "task_id": "example-task-1",
        "title": "example task",
        "repository_url": "https://github.com/example/repo",
        "commit_sha": "abcdef123456",
        "dependency": "pytest-mock",
        "from_version": "3.10.0",
        "to_version": "3.11.1",
    })
    client = TestClient(app)

    # With supported_demo policy, example tasks are hidden
    resp_filtered = client.get("/api/tasks?policy=supported_demo")
    assert resp_filtered.status_code == 200
    ids_filtered = [t["task_id"] for t in resp_filtered.json()["tasks"]]
    assert "TASK-DEMO-SHOP" in ids_filtered
    assert "example-task-1" not in ids_filtered

    # With policy=all or include_acceptance=true, all tasks are returned
    resp_all = client.get("/api/tasks?policy=all")
    assert resp_all.status_code == 200
    ids_all = [t["task_id"] for t in resp_all.json()["tasks"]]
    assert "TASK-DEMO-SHOP" in ids_all
    assert "example-task-1" in ids_all


def test_resolve_branches_invalid_url():
    from src.custom_validation import resolve_repository_branches

    with pytest.raises(ValueError, match="Repository URL must be a public GitHub HTTPS URL"):
        resolve_repository_branches("https://gitlab.com/owner/repo")


def test_resolve_branches_mocked(monkeypatch):
    import subprocess
    from src.custom_validation import resolve_repository_branches

    sample_output = (
        "ref: refs/heads/main\tHEAD\n"
        "1111111111111111111111111111111111111111\tHEAD\n"
        "2222222222222222222222222222222222222222\trefs/heads/feature\n"
        "1111111111111111111111111111111111111111\trefs/heads/main\n"
    )

    def mock_run(*args, **kwargs):
        return subprocess.CompletedProcess(args=args[0], returncode=0, stdout=sample_output, stderr="")

    monkeypatch.setattr(subprocess, "run", mock_run)

    res = resolve_repository_branches("https://github.com/my-org/my-project")
    assert res.default_branch == "main"
    assert len(res.branches) == 2
    assert res.branches[0].name == "main"
    assert res.branches[0].commit_sha == "1111111111111111111111111111111111111111"
    assert res.branches[1].name == "feature"
    assert res.branches[1].commit_sha == "2222222222222222222222222222222222222222"


def test_verify_branch_pinned_sha_mocked(monkeypatch):
    import subprocess
    from src.custom_validation import verify_branch_pinned_sha

    sample_output = "8c400721558392a23b3af71766f673da02f80040\trefs/heads/main\n"

    def mock_run(*args, **kwargs):
        return subprocess.CompletedProcess(args=args[0], returncode=0, stdout=sample_output, stderr="")

    monkeypatch.setattr(subprocess, "run", mock_run)

    matched = verify_branch_pinned_sha(
        "https://github.com/SGOD-pro/repo-medic.git",
        "main",
        "8c400721558392a23b3af71766f673da02f80040",
    )
    assert matched is True

    mismatched = verify_branch_pinned_sha(
        "https://github.com/SGOD-pro/repo-medic.git",
        "main",
        "0000000000000000000000000000000000000000",
    )
    assert mismatched is False


def test_api_resolve_branches_endpoint(test_app_and_repo, monkeypatch):
    import subprocess
    app, repo = test_app_and_repo
    client = TestClient(app)

    sample_output = (
        "ref: refs/heads/main\tHEAD\n"
        "8c400721558392a23b3af71766f673da02f80040\trefs/heads/main\n"
    )

    def mock_run(*args, **kwargs):
        return subprocess.CompletedProcess(args=args[0], returncode=0, stdout=sample_output, stderr="")

    monkeypatch.setattr(subprocess, "run", mock_run)

    resp = client.post(
        "/api/custom/resolve-branches",
        json={"repository_url": "https://github.com/SGOD-pro/repo-medic.git"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["default_branch"] == "main"
    assert len(data["branches"]) == 1
    assert data["branches"][0]["name"] == "main"
    assert data["branches"][0]["commit_sha"] == "8c400721558392a23b3af71766f673da02f80040"


def test_custom_execution_flow_when_enabled(test_app_and_repo, monkeypatch):
    from src.config import settings
    import subprocess

    app, repo = test_app_and_repo
    client = TestClient(app)

    # Enable custom execution
    monkeypatch.setattr(settings, "repomedic_custom_execution_enabled", True)

    sample_output = "8c400721558392a23b3af71766f673da02f80040\trefs/heads/main\n"

    def mock_run(*args, **kwargs):
        return subprocess.CompletedProcess(args=args[0], returncode=0, stdout=sample_output, stderr="")

    monkeypatch.setattr(subprocess, "run", mock_run)

    config = sample_valid_config()
    payload = {
        "config": config.model_dump(),
        "branch": "main",
        "search_mode": "sequential",
        "idempotency_key": "custom-key-001",
    }

    # First submission
    resp1 = client.post("/api/custom/run", json=payload)
    assert resp1.status_code == 202
    data1 = resp1.json()
    run_id = data1["run_id"]
    task_id = data1["task_id"]
    assert task_id.startswith("TASK-CUSTOM-")

    # Idempotent replay with same key and payload returns identical run
    resp2 = client.post("/api/custom/run", json=payload)
    assert resp2.status_code in (200, 202)
    data2 = resp2.json()
    assert data2["run_id"] == run_id

    # Verify task was persisted in repository
    task = repo.get_task(task_id)
    assert task is not None
    assert task.repository_url == config.repository_url
    assert task.commit_sha == config.commit_sha
