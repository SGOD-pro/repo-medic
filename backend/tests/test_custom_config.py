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
