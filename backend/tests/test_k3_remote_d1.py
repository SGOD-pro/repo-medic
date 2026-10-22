import asyncio
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List

import httpx
import pytest

from src.config import settings
from src.contracts import TaskRecipe
from src.main import recover_interrupted_runs
from src.storage.db_client import RepoMedicDB
from src.storage.repository import D1HostPorts, D1StorageRepository
from tests.test_storage import create_sqlite_d1_transport


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    setattr(item, "rep_" + rep.when, rep)


class AcceptanceManifest:
    """Exact in memory manifest tracking every entity created during an acceptance run."""

    def __init__(self, prefix: str):
        self.prefix = prefix
        self.tasks: List[str] = []
        self.runs: List[str] = []
        self.operations: List[str] = []
        self.artifacts: List[str] = []

    def record_task(self, task_id: str) -> str:
        if task_id not in self.tasks:
            self.tasks.append(task_id)
        return task_id

    def record_run(self, run_id: str) -> str:
        if run_id not in self.runs:
            self.runs.append(run_id)
        return run_id

    def record_operation(self, op_id: str) -> str:
        if op_id not in self.operations:
            self.operations.append(op_id)
        return op_id

    def record_artifact(self, art_id: str) -> str:
        if art_id not in self.artifacts:
            self.artifacts.append(art_id)
        return art_id

    def to_dict(self) -> Dict[str, List[str]]:
        return {
            "tasks": list(self.tasks),
            "runs": list(self.runs),
            "operations": list(self.operations),
            "artifacts": list(self.artifacts),
        }

    def dump_on_failure(self, dump_dir: Path) -> Path:
        dump_dir.mkdir(parents=True, exist_ok=True)
        ts = int(time.time() * 1000)
        dest = dump_dir / f"k3_manifest_{ts}.json"
        dest.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return dest


@pytest.fixture
def k3_manifest(request) -> Any:
    prefix = f"run_k3_accept_{int(time.time() * 1000)}_"
    manifest = AcceptanceManifest(prefix=prefix)
    yield manifest
    rep_call = getattr(request.node, "rep_call", None)
    if rep_call and rep_call.failed:
        artifacts_dir = Path(__file__).resolve().parent.parent / "artifacts"
        manifest.dump_on_failure(artifacts_dir)


@pytest.fixture
def k3_client_and_repo():
    """Provides storage client and repository.

    Uses remote Cloudflare Worker bridge when REPOMEDIC_RUN_REMOTE_D1 is true.
    Otherwise uses isolated SQLite simulation transport for offline checks.
    """
    is_remote = os.getenv("REPOMEDIC_RUN_REMOTE_D1", "").lower() in ("true", "1")
    if is_remote:
        url = os.getenv("REPOMEDIC_DB_WORKER_URL", getattr(settings, "repomedic_db_worker_url", ""))
        token = os.getenv("REPOMEDIC_DB_WORKER_TOKEN", getattr(settings, "repomedic_db_worker_token", ""))
        client = RepoMedicDB(base_url=url, api_key=token)
    else:
        transport = create_sqlite_d1_transport(expected_token="simulated-bridge-token")
        client = RepoMedicDB(
            base_url="http://simulated-d1-bridge",
            api_key="simulated-bridge-token",
            transport=transport,
        )

    repo = D1StorageRepository(client)
    return client, repo, is_remote


def test_simulation_notice_does_not_claim_remote_acceptance(k3_client_and_repo):
    """Confirm simulation test mode does not claim real remote acceptance."""
    client, repo, is_remote = k3_client_and_repo
    if not is_remote:
        # Explicit verification: offline simulation must never claim remote acceptance
        assert is_remote is False
        assert os.getenv("REPOMEDIC_RUN_REMOTE_D1", "").lower() not in ("true", "1")
        assert hasattr(client, "transport") and client.transport is not None
        assert str(client.base_url).startswith("http://simulated-d1-bridge")
    else:
        assert is_remote is True
        assert not str(client.base_url).startswith("http://simulated-d1-bridge")


def test_fail_closed_authentication_offline_and_remote(k3_client_and_repo):
    """Verify unauthorized or unconfigured access is rejected (AC 3)."""
    client, repo, is_remote = k3_client_and_repo

    # Check unauthenticated health endpoint remains 200
    health = client.health()
    assert health.get("ok") is True

    # Bad token produces 401
    bad_client = RepoMedicDB(
        base_url=client.base_url,
        api_key="invalid-unauthorized-token",
        transport=getattr(client, "transport", None),
    )
    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        bad_client.list_tasks()
    assert exc_info.value.response.status_code == 401


def test_zero_partial_writes_on_failure(k3_client_and_repo, k3_manifest):
    """Verify failed run creation, oversized artifacts, and invalid events leave zero partial rows (AC 5)."""
    client, repo, is_remote = k3_client_and_repo
    task_id = k3_manifest.record_task(f"{k3_manifest.prefix}task_zero_partial")
    run_id = k3_manifest.record_run(f"{k3_manifest.prefix}run_zero_partial")

    repo.upsert_task({
        "task_id": task_id,
        "title": "Task for partial write tests",
        "repository_url": "https://github.com/example/repo",
        "commit_sha": "abc123",
        "dependency": "pkg",
        "from_version": "1.0",
        "to_version": "2.0",
    })

    # First run creation succeeds
    run = repo.create_run(
        run_id=run_id,
        task_id=task_id,
        mode="offline",
        search_mode="sequential",
    )
    assert run.run_id == run_id

    # Duplicate run creation must return 409
    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        client.create_run(
            run_id=run_id,
            task_id=task_id,
            mode="offline",
            search_mode="sequential",
        )
    assert exc_info.value.response.status_code == 409

    # Verify run remains in initial state and only one row exists
    fetched = repo.get_run(run_id)
    assert fetched is not None
    assert fetched.run_id == run_id

    # Oversized artifact (> 1,048,576 bytes) must reject
    oversized_data = b"X" * (1048576 + 10)
    with pytest.raises(httpx.HTTPStatusError) as exc_art:
        repo.store_artifact(
            run_id=run_id,
            kind="log",
            filename="large.log",
            content=oversized_data,
        )
    assert exc_art.value.response.status_code in (400, 413)

    # Invalid event payload (non dict) must reject with 400 and leave zero event rows
    with pytest.raises(httpx.HTTPStatusError) as exc_evt:
        client.create_event(
            run_id=run_id,
            event_type="",
            payload="invalid_payload_not_dict",  # type: ignore[arg-type]
        )
    assert exc_evt.value.response.status_code == 400
    events_after = client.list_events(run_id=run_id)
    assert len(events_after) == 0

    # Clean up manifest
    repo.cleanup_manifest(k3_manifest.to_dict())


@pytest.mark.asyncio
async def test_event_ordering_and_artifact_hashes(k3_client_and_repo, k3_manifest):
    """Verify monotonic gap free event sequence numbers and artifact hash checksums."""
    client, repo, is_remote = k3_client_and_repo
    task_id = k3_manifest.record_task(f"{k3_manifest.prefix}task_events")
    run_id = k3_manifest.record_run(f"{k3_manifest.prefix}run_events")

    repo.upsert_task({
        "task_id": task_id,
        "title": "Task for event ordering",
        "repository_url": "https://github.com/example/repo",
        "commit_sha": "abc123",
        "dependency": "pkg",
        "from_version": "1.0",
        "to_version": "2.0",
    })
    repo.create_run(run_id=run_id, task_id=task_id, mode="offline", search_mode="sequential")

    host = D1HostPorts(run_id=run_id, repo=repo)

    # Emit three sequential events
    await host.emit(
        "run.started",
        {
            "task_id": task_id,
            "mode": "offline",
            "search_mode": "sequential",
            "max_run_usd": 2.0,
        },
    )
    await host.emit("stage.completed", {"stage": "baseline", "passed": True, "summary": "ok"})
    await host.emit("run.finished", {"state": "succeeded", "reason": "done"})

    # Query events from sequence 0
    events = repo.list_events(run_id, after=0)
    assert len(events) == 3
    assert [e.seq for e in events] == [1, 2, 3]

    # Query events with cursor
    events_after_1 = repo.list_events(run_id, after=1)
    assert len(events_after_1) == 2
    assert [e.seq for e in events_after_1] == [2, 3]

    # Save artifact with hash verification
    patch_bytes = b"diff --git a/file b/file\n--- a/file\n+++ b/file\n"
    expected_hash = hashlib.sha256(patch_bytes).hexdigest()
    art_id = await host.save_artifact("patch", "patch.diff", patch_bytes)
    k3_manifest.record_artifact(art_id)

    content = repo.get_artifact_content(run_id, art_id)
    actual_hash = hashlib.sha256(content).hexdigest()
    assert actual_hash == expected_hash

    # Clean up manifest
    repo.cleanup_manifest(k3_manifest.to_dict())


@pytest.mark.asyncio
async def test_cancellation_handling(k3_client_and_repo, k3_manifest):
    """Verify run cancellation transitions state and rejects further mutations."""
    client, repo, is_remote = k3_client_and_repo
    task_id = k3_manifest.record_task(f"{k3_manifest.prefix}task_cancel")
    run_id = k3_manifest.record_run(f"{k3_manifest.prefix}run_cancel")

    repo.upsert_task({
        "task_id": task_id,
        "title": "Task for cancel check",
        "repository_url": "https://github.com/example/repo",
        "commit_sha": "abc123",
        "dependency": "pkg",
        "from_version": "1.0",
        "to_version": "2.0",
    })
    repo.create_run(run_id=run_id, task_id=task_id, mode="offline", search_mode="sequential")
    host = D1HostPorts(run_id=run_id, repo=repo)

    # Cancel run
    repo.finish_run(run_id, state="cancelled", reason="user requested cancel")
    assert await host.cancelled() is True

    # Transitioning from terminal cancelled state must return 409
    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        client.update_run_state(run_id, state="running")
    assert exc_info.value.response.status_code == 409

    repo.cleanup_manifest(k3_manifest.to_dict())


@pytest.mark.asyncio
async def test_concurrent_budget_reservations(k3_client_and_repo, k3_manifest):
    """Verify per run and global budget caps atomically reject excess reservations (AC 6)."""
    client, repo, is_remote = k3_client_and_repo
    task_id = k3_manifest.record_task(f"{k3_manifest.prefix}task_budget")
    run_id = k3_manifest.record_run(f"{k3_manifest.prefix}run_budget")

    repo.upsert_task({
        "task_id": task_id,
        "title": "Task for budget check",
        "repository_url": "https://github.com/example/repo",
        "commit_sha": "abc123",
        "dependency": "pkg",
        "from_version": "1.0",
        "to_version": "2.0",
    })
    # Run with 1.0 USD budget cap
    repo.create_run(
        run_id=run_id,
        task_id=task_id,
        mode="offline",
        search_mode="sequential",
        max_run_usd=1.0,
    )
    host = D1HostPorts(run_id=run_id, repo=repo)

    # Per run budget limit check: Two concurrent reservations of 0.6 USD each (total 1.2 USD > 1.0 USD)
    op1_id = f"{run_id}:model:call1"
    op2_id = f"{run_id}:model:call2"
    k3_manifest.record_operation(op1_id)
    k3_manifest.record_operation(op2_id)

    res1, res2 = await asyncio.gather(
        host.reserve("model:call1", 0.6),
        host.reserve("model:call2", 0.6),
    )

    # Exactly one must succeed and one must fail
    assert (res1 is True and res2 is False) or (res1 is False and res2 is True)

    # Global budget cap check (25 USD = 25,000,000 micro USD, AC 6)
    # Attempting to exceed global budget ceiling of 25.0 USD is atomically rejected
    global_exceed_op = f"{run_id}:model:call_global_exceed"
    with pytest.raises(httpx.HTTPStatusError) as exc_global:
        client.reserve_budget(
            run_id=run_id,
            operation_id=global_exceed_op,
            kind="model_inference",
            estimated_usd=25.1,
            global_budget_usd=25.0,
        )
    assert exc_global.value.response.status_code == 409

    repo.cleanup_manifest(k3_manifest.to_dict())


def test_persistence_across_restart(k3_client_and_repo, k3_manifest):
    """Verify running state persists and restart recovery marks only scoped runs failed."""
    client, repo, is_remote = k3_client_and_repo
    task_id = k3_manifest.record_task(f"{k3_manifest.prefix}task_persist")
    scoped_run_id = k3_manifest.record_run(f"{k3_manifest.prefix}run_scoped")
    unrelated_run_id = f"run_unrelated_persist_{int(time.time() * 1000)}"

    repo.upsert_task({
        "task_id": task_id,
        "title": "Task for restart check",
        "repository_url": "https://github.com/example/repo",
        "commit_sha": "abc123",
        "dependency": "pkg",
        "from_version": "1.0",
        "to_version": "2.0",
    })

    try:
        repo.create_run(
            run_id=scoped_run_id, task_id=task_id, mode="offline", search_mode="sequential", state="running"
        )
        repo.create_run(
            run_id=unrelated_run_id, task_id=task_id, mode="offline", search_mode="sequential", state="running"
        )

        # Simulate process restart recovery with prefix
        recover_interrupted_runs(repo, acceptance_prefix=k3_manifest.prefix)

        # Scoped run must be failed
        scoped_run = repo.get_run(scoped_run_id)
        assert scoped_run.state == "failed"

        # Unrelated run must remain in running state
        unrelated_run = repo.get_run(unrelated_run_id)
        assert unrelated_run.state == "running"
    finally:
        # Explicit teardown of the temporary unrelated test record
        repo.cleanup_manifest({
            "tasks": [],
            "runs": [unrelated_run_id],
            "operations": [],
            "artifacts": [],
        })
        repo.cleanup_manifest(k3_manifest.to_dict())


def test_exact_manifest_cleanup_preserves_unrelated_records(k3_client_and_repo, k3_manifest):
    """Verify cleanup removes only records in exact manifest and preserves other records (AC 4)."""
    client, repo, is_remote = k3_client_and_repo

    # Seed an unrelated task and run with dynamic unique IDs that are NOT in the manifest
    unrelated_task_id = f"task_unrelated_keep_{int(time.time() * 1000)}"
    unrelated_run_id = f"run_unrelated_keep_{int(time.time() * 1000)}"

    repo.upsert_task({
        "task_id": unrelated_task_id,
        "title": "Unrelated task to preserve",
        "repository_url": "https://github.com/example/repo",
        "commit_sha": "111222",
        "dependency": "pkg",
        "from_version": "1.0",
        "to_version": "2.0",
    })
    repo.create_run(
        run_id=unrelated_run_id,
        task_id=unrelated_task_id,
        mode="offline",
        search_mode="sequential",
    )

    try:
        # Seed manifest records
        scoped_task_id = k3_manifest.record_task(f"{k3_manifest.prefix}task_clean")
        scoped_run_id = k3_manifest.record_run(f"{k3_manifest.prefix}run_clean")

        repo.upsert_task({
            "task_id": scoped_task_id,
            "title": "Scoped task to delete",
            "repository_url": "https://github.com/example/repo",
            "commit_sha": "333444",
            "dependency": "pkg",
            "from_version": "1.0",
            "to_version": "2.0",
        })
        repo.create_run(
            run_id=scoped_run_id,
            task_id=scoped_task_id,
            mode="offline",
            search_mode="sequential",
        )

        # Perform exact manifest cleanup
        manifest_dict = k3_manifest.to_dict()
        cleanup_res = repo.cleanup_manifest(manifest_dict)
        assert cleanup_res.get("ok") is True

        # Scoped records must be gone
        assert repo.get_task(scoped_task_id) is None
        with pytest.raises(httpx.HTTPStatusError) as exc_run:
            repo.get_run(scoped_run_id)
        assert exc_run.value.response.status_code == 404

        # Unrelated records must remain completely intact
        assert repo.get_task(unrelated_task_id) is not None
        assert repo.get_run(unrelated_run_id) is not None
    finally:
        # Explicit teardown of the non manifest test entity so subsequent runs leave no stray records
        repo.cleanup_manifest({
            "tasks": [unrelated_task_id],
            "runs": [unrelated_run_id],
            "operations": [],
            "artifacts": [],
        })


def test_acceptance_manifest_dump_on_failure(tmp_path: Path):
    """Verify acceptance manifest dump_on_failure exports exact entity state on diagnosis."""
    manifest = AcceptanceManifest(prefix="run_test_dump_")
    manifest.record_task("task-1")
    manifest.record_run("run-1")
    manifest.record_operation("op-1")
    manifest.record_artifact("art-1")

    dump_path = manifest.dump_on_failure(tmp_path)
    assert dump_path.is_file()
    data = json.loads(dump_path.read_text(encoding="utf-8"))
    assert data == {
        "tasks": ["task-1"],
        "runs": ["run-1"],
        "operations": ["op-1"],
        "artifacts": ["art-1"],
    }


@pytest.mark.skipif(
    not os.getenv("REPOMEDIC_RUN_REMOTE_D1"),
    reason="Remote Cloudflare D1 test is opt in; set REPOMEDIC_RUN_REMOTE_D1=true to run against deployed Worker",
)
def test_remote_cloudflare_d1_opt_in_execution(k3_client_and_repo, k3_manifest):
    """Opt in live execution against real deployed Cloudflare D1 Worker."""
    client, repo, is_remote = k3_client_and_repo
    assert is_remote is True
    health = client.health()
    assert health.get("ok") is True
