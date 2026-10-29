import json
import pytest
from fastapi.testclient import TestClient
from src.main import create_app
from src.contracts import TaskSummary
from src.storage.turso_client import TursoClient
from src.storage.repository import D1StorageRepository


def test_api_list_tasks_returns_declared_metadata():
    app = create_app()
    client = TestClient(app)
    res = client.get("/api/tasks?policy=supported_demo")
    assert res.status_code == 200
    data = res.json()
    assert "tasks" in data
    tasks = {t["task_id"]: t for t in data["tasks"]}

    # Verify all 4 demo tasks are present
    demo_ids = ["TASK-DEMO-SHOP", "TASK-DEMO-CLICK", "TASK-DEMO-PYDANTIC", "TASK-DEMO-JWT"]
    for did in demo_ids:
        assert did in tasks, f"Expected {did} to be in tasks"
        t = tasks[did]
        assert t["expected_failure"] is not None and len(t["expected_failure"]) > 0
        assert isinstance(t["test_command"], list) and len(t["test_command"]) > 0
        assert isinstance(t["allowed_source_paths"], list) and len(t["allowed_source_paths"]) > 0
        assert isinstance(t["tests_count"], int) and t["tests_count"] > 0
        assert isinstance(t["baseline_time"], str) and len(t["baseline_time"]) > 0

    # Specific metadata assertions for each demo task
    shop = tasks["TASK-DEMO-SHOP"]
    assert "AttributeError: 'Engine' object has no attribute 'execute'" in shop["expected_failure"]
    assert shop["tests_count"] == 1
    assert "0.16s" in shop["baseline_time"]
    assert "src/shop/database.py" in shop["allowed_source_paths"]

    jwt = tasks["TASK-DEMO-JWT"]
    assert "AttributeError: 'str' object has no attribute 'decode'" in jwt["expected_failure"]
    assert jwt["tests_count"] == 3
    assert "0.15s" in jwt["baseline_time"]
    assert "src/auth/tokens.py" in jwt["allowed_source_paths"]


def test_storage_upsert_and_retrieve_metadata_in_memory_turso():
    client = TursoClient(database=":memory:")
    repo = D1StorageRepository(client=client)

    task_payload = {
        "task_id": "TASK-TEST-METADATA",
        "title": "Test Metadata Task",
        "repository_url": "https://github.com/SGOD-pro/repo-medic.git",
        "commit_sha": "abcdef1234567890abcdef1234567890abcdef12",
        "dependency": "dummy_pkg",
        "from_version": "1.0.0",
        "to_version": "2.0.0",
        "test_command": ["pytest", "tests/dummy"],
        "allowed_source_paths": ["src/dummy.py"],
        "expected_failure": "DummyError: sample failure",
        "tests_count": 5,
        "baseline_time": "0.42s (Python 3.12)",
    }

    repo.upsert_task(task_payload)

    # Fetch through repository get_task
    fetched = repo.get_task("TASK-TEST-METADATA")
    assert fetched is not None
    assert fetched.expected_failure == "DummyError: sample failure"
    assert fetched.test_command == ["pytest", "tests/dummy"]
    assert fetched.allowed_source_paths == ["src/dummy.py"]
    assert fetched.tests_count == 5
    assert fetched.baseline_time == "0.42s (Python 3.12)"

    # Verify through list_tasks
    all_tasks = {t.task_id: t for t in repo.list_tasks()}
    assert "TASK-TEST-METADATA" in all_tasks
    t_summary = all_tasks["TASK-TEST-METADATA"]
    assert t_summary.expected_failure == "DummyError: sample failure"
    assert t_summary.tests_count == 5


def test_storage_handles_missing_and_malformed_metadata_gracefully():
    client = TursoClient(database=":memory:")
    repo = D1StorageRepository(client=client)

    # 1. Task with no recipe metadata at all
    client.upsert_task({
        "task_id": "TASK-NO-RECIPE",
        "title": "No Recipe Task",
        "repository_url": "https://github.com/SGOD-pro/repo-medic.git",
        "commit_sha": "1111222233334444555566667777888899990000",
        "dependency": "pkg",
        "from_version": "1.0",
        "to_version": "2.0",
    })

    t_empty = repo.get_task("TASK-NO-RECIPE")
    assert t_empty is not None
    assert t_empty.expected_failure is None
    assert t_empty.test_command is None
    assert t_empty.allowed_source_paths is None
    assert t_empty.tests_count is None
    assert t_empty.baseline_time is None

    # 2. Directly insert raw corrupted recipe_json into SQLite
    client._conn.execute(
        """INSERT INTO tasks (task_id, title, repository_url, commit_sha, dependency, from_version, to_version, recipe_json, created_at)
           VALUES ('TASK-MALFORMED', 'Malformed Task', 'https://github.com/SGOD-pro/repo-medic.git', '1111222233334444555566667777888899990000', 'pkg', '1.0', '2.0', '{corrupted json string', '2026-10-29T00:00:00Z')"""
    )

    t_malformed = repo.get_task("TASK-MALFORMED")
    assert t_malformed is not None
    assert t_malformed.expected_failure is None
    assert t_malformed.tests_count is None
    assert t_malformed.baseline_time is None
