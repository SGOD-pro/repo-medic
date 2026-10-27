import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.contracts import RepairRequest, RepairResult, TaskRecipe
from src.lambda_api import handler as lambda_api_handler
from src.lambda_worker import handler as lambda_worker_handler, process_sqs_records
from src.main import create_app
from src.storage.db_client import RepoMedicDB
from src.storage.repository import D1StorageRepository
from tests.test_storage import create_sqlite_d1_transport


@pytest.fixture
def mock_repo():
    transport = create_sqlite_d1_transport(expected_token="test-bridge-token")
    mock_db = RepoMedicDB(
        base_url="http://test-bridge",
        api_key="test-bridge-token",
        transport=transport,
    )
    repo = D1StorageRepository(mock_db)
    repo.upsert_task({
        "task_id": "TASK-091",
        "title": "Upgrade SQLAlchemy",
        "repository_url": "https://github.com/SGOD-pro/repo-medic",
        "commit_sha": "453a0b6c6b125177504cdd941902b8d48266ed1c",
        "dependency": "sqlalchemy",
        "from_version": "1.4.48",
        "to_version": "2.0.19",
    })
    return repo


def test_lambda_api_handler():
    """Verify Mangum API Lambda handler processes HTTP events."""
    event = {
        "version": "2.0",
        "routeKey": "GET /api/tasks",
        "rawPath": "/api/tasks",
        "rawQueryString": "",
        "headers": {
            "host": "test.execute-api.us-east-1.amazonaws.com",
            "user-agent": "test-agent",
        },
        "requestContext": {
            "http": {
                "method": "GET",
                "path": "/api/tasks",
                "protocol": "HTTP/1.1",
                "sourceIp": "127.0.0.1",
                "userAgent": "test-agent",
            }
        },
        "isBase64Encoded": False,
    }
    response = lambda_api_handler(event, None)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "tasks" in body
    assert any(t["task_id"] == "TASK-091" for t in body["tasks"])


@pytest.mark.asyncio
async def test_lambda_worker_atomic_cas_claim(mock_repo):
    """Verify worker Lambda executes atomic CAS on queued run."""
    run = mock_repo.create_run(
        run_id="run_cas_test_1",
        task_id="TASK-091",
        mode="offline",
        search_mode="sequential",
        state="queued",
    )
    assert run.state == "queued"

    repair_mock = AsyncMock(
        return_value=RepairResult(
            run_id="run_cas_test_1",
            state="succeeded",
            reason="Verified offline fix",
        )
    )

    records = [
        {
            "messageId": "msg-001",
            "body": json.dumps({"run_id": "run_cas_test_1"}),
        }
    ]

    failures = await process_sqs_records(
        records=records,
        repo=mock_repo,
        repair_fn=repair_mock,
    )

    assert failures == []
    repair_mock.assert_awaited_once()

    finished_run = mock_repo.get_run("run_cas_test_1")
    assert finished_run.state == "succeeded"


@pytest.mark.asyncio
async def test_lambda_worker_duplicate_message_ignored(mock_repo):
    """Verify worker Lambda safely ignores duplicate SQS deliveries without double execution."""
    mock_repo.create_run(
        run_id="run_already_running",
        task_id="TASK-091",
        mode="offline",
        search_mode="sequential",
        state="running",
    )

    repair_mock = AsyncMock()

    records = [
        {
            "messageId": "msg-dup-001",
            "body": json.dumps({"run_id": "run_already_running"}),
        }
    ]

    failures = await process_sqs_records(
        records=records,
        repo=mock_repo,
        repair_fn=repair_mock,
    )

    assert failures == []
    # Repair logic should NEVER be invoked for already-running run
    repair_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_lambda_worker_terminal_state_ignored(mock_repo):
    """Verify worker Lambda safely ignores messages for already completed or cancelled runs."""
    mock_repo.create_run(
        run_id="run_already_succeeded",
        task_id="TASK-091",
        mode="offline",
        search_mode="sequential",
        state="succeeded",
    )

    repair_mock = AsyncMock()

    records = [
        {
            "messageId": "msg-dup-002",
            "body": json.dumps({"run_id": "run_already_succeeded"}),
        }
    ]

    failures = await process_sqs_records(
        records=records,
        repo=mock_repo,
        repair_fn=repair_mock,
    )

    assert failures == []
    repair_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_lambda_worker_unknown_run_discarded(mock_repo):
    """Verify worker Lambda discards messages referencing nonexistent runs."""
    records = [
        {
            "messageId": "msg-unknown",
            "body": json.dumps({"run_id": "run_nonexistent_999"}),
        }
    ]
    failures = await process_sqs_records(records=records, repo=mock_repo)
    assert failures == []


def test_lambda_worker_top_level_handler(mock_repo, monkeypatch):
    """Verify standard Lambda SQS event entrypoint."""
    mock_repo.create_run(
        run_id="run_handler_test",
        task_id="TASK-091",
        mode="offline",
        search_mode="sequential",
        state="queued",
    )

    event = {
        "Records": [
            {
                "messageId": "msg-12345",
                "body": json.dumps({"run_id": "run_handler_test"}),
            }
        ]
    }

    # Patch repo lookup inside lambda_worker
    monkeypatch.setattr("src.lambda_worker.D1StorageRepository", lambda: mock_repo)

    result = lambda_worker_handler(event, None)
    assert result == {"batchItemFailures": []}

    run = mock_repo.get_run("run_handler_test")
    assert run.state in ("succeeded", "failed")
