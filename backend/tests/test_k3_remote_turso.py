import asyncio
import hashlib
import json
import os
import socket
import subprocess
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List
import pytest

from src.config import settings
from src.main import recover_interrupted_runs
from src.storage.exceptions import StorageConflictError, StorageError, StorageLimitExceededError
from src.storage.repository import TursoHostPorts, TursoStorageRepository
from src.storage.turso_client import TursoClient


class TursoAcceptanceManifest:
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
        dest = dump_dir / f"k3_turso_manifest_{ts}.json"
        dest.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return dest


@pytest.fixture
def k3_turso_manifest(request, k3_turso_client_and_repo) -> Any:
    prefix = f"run_k3_turso_{int(time.time() * 1000)}_"
    manifest = TursoAcceptanceManifest(prefix=prefix)
    client, repo, is_remote = k3_turso_client_and_repo
    tests_failed_before = request.session.testsfailed

    yield manifest

    tests_failed_after = request.session.testsfailed
    test_failed = tests_failed_after > tests_failed_before
    if test_failed:
        artifacts_dir = Path(__file__).resolve().parent.parent / "artifacts"
        manifest.dump_on_failure(artifacts_dir)
    else:
        repo.cleanup_manifest(manifest.to_dict())


@pytest.fixture
def k3_turso_client_and_repo(tmp_path):
    """Provides Turso client and repository.

    Uses remote Turso database when REPOMEDIC_RUN_REMOTE_TURSO is true.
    Otherwise uses isolated temporary libSQL database for offline checks.
    """
    is_remote = os.getenv("REPOMEDIC_RUN_REMOTE_TURSO", "").lower() in ("true", "1")
    if is_remote:
        url = os.getenv("TURSO_DATABASE_URL", getattr(settings, "turso_database_url", ""))
        token = os.getenv("TURSO_AUTH_TOKEN", getattr(settings, "turso_auth_token", ""))
        if not url:
            pytest.fail("REPOMEDIC_RUN_REMOTE_TURSO=true but TURSO_DATABASE_URL is not configured")
        if not url.startswith(("libsql://", "https://", "http://")):
            pytest.fail(f"REPOMEDIC_RUN_REMOTE_TURSO=true requires a remote database URL, got '{url}'")
        if not token:
            pytest.fail("REPOMEDIC_RUN_REMOTE_TURSO=true but TURSO_AUTH_TOKEN is not configured")
        client = TursoClient(database=url, auth_token=token)
    else:
        db_file = str(tmp_path / "k3_turso_local.db")
        client = TursoClient(database=db_file)

    repo = TursoStorageRepository(client=client)
    yield client, repo, is_remote
    client.close()


def test_simulation_notice_does_not_claim_remote_acceptance(k3_turso_client_and_repo):
    """Confirm simulation test mode does not claim real remote acceptance."""
    client, repo, is_remote = k3_turso_client_and_repo
    if not is_remote:
        assert is_remote is False
        assert os.getenv("REPOMEDIC_RUN_REMOTE_TURSO", "").lower() not in ("true", "1")
        assert not client.database.startswith(("libsql://", "https://", "http://"))
    else:
        assert is_remote is True
        assert client.database.startswith(("libsql://", "https://", "http://"))


def test_turso_preflight_configuration(k3_turso_client_and_repo):
    """Verify Turso health check and dialect availability."""
    client, repo, is_remote = k3_turso_client_and_repo
    health = client.health()
    assert health.get("ok") is True
    assert health.get("engine") == "libsql"


def test_acceptance_prefix_isolation(k3_turso_client_and_repo, k3_turso_manifest):
    """Verify acceptance runs remain strictly isolated by prefix."""
    client, repo, is_remote = k3_turso_client_and_repo
    prefix = k3_turso_manifest.prefix

    task_id = k3_turso_manifest.record_task(f"{prefix}task_1")
    repo.upsert_task({
        "task_id": task_id,
        "title": "Isolated Task",
        "repository_url": "https://github.com/example/repo.git",
        "commit_sha": "abc1234",
        "dependency": "pkg",
        "from_version": "1.0",
        "to_version": "2.0",
    })

    run_id = k3_turso_manifest.record_run(f"{prefix}run_1")
    repo.create_run(
        run_id=run_id,
        task_id=task_id,
        mode="offline",
        search_mode="sequential",
    )

    scoped_runs = repo.list_runs(run_prefix=prefix)
    assert len(scoped_runs) == 1
    assert scoped_runs[0].run_id == run_id

    unmatched_runs = repo.list_runs(run_prefix=f"{prefix}nonexistent_")
    assert len(unmatched_runs) == 0


def test_zero_partial_writes_on_failure(k3_turso_client_and_repo, k3_turso_manifest):
    """Verify over-budget reservations, duplicate runs, and oversized artifacts leave zero partial records."""
    client, repo, is_remote = k3_turso_client_and_repo
    prefix = k3_turso_manifest.prefix

    task_id = k3_turso_manifest.record_task(f"{prefix}task_zero_write")
    repo.upsert_task({
        "task_id": task_id,
        "title": "Zero Write Task",
        "repository_url": "https://github.com/example/repo.git",
        "commit_sha": "1234567",
        "dependency": "pkg",
        "from_version": "1.0",
        "to_version": "2.0",
    })

    run_id = k3_turso_manifest.record_run(f"{prefix}run_zw")
    repo.create_run(run_id=run_id, task_id=task_id, mode="offline", search_mode="sequential", max_run_usd=1.0)

    # 1. Over-budget reservation must be rejected
    with pytest.raises(StorageConflictError):
        client.reserve_budget(
            run_id=run_id,
            operation_id="op_over_budget",
            kind="model",
            estimated_usd=1.50,
            global_budget_usd=25.0,
        )

    # Verify no partial operation record was inserted for this run
    run = repo.get_run(run_id)
    assert run.usage.estimated_usd == 0

    # 2. Duplicate run must be rejected
    with pytest.raises(StorageConflictError):
        repo.create_run(run_id=run_id, task_id=task_id, mode="offline", search_mode="sequential")

    # 3. Oversized artifact must be rejected
    oversized = b"x" * (1048576 + 1)
    with pytest.raises(StorageLimitExceededError):
        repo.store_artifact(run_id=run_id, kind="patch", filename="huge.diff", content=oversized)

    run = repo.get_run(run_id)
    assert len(run.artifacts) == 0


def test_concurrent_budget_reservations(k3_turso_client_and_repo, k3_turso_manifest):
    """Verify concurrent reservations atomically enforce the budget cap."""
    client, repo, is_remote = k3_turso_client_and_repo
    prefix = k3_turso_manifest.prefix

    task_id = k3_turso_manifest.record_task(f"{prefix}task_concurrent")
    repo.upsert_task({
        "task_id": task_id,
        "title": "Concurrent Task",
        "repository_url": "https://github.com/example/repo.git",
        "commit_sha": "abc1234",
        "dependency": "pkg",
        "from_version": "1.0",
        "to_version": "2.0",
    })

    run_id = k3_turso_manifest.record_run(f"{prefix}run_conc")
    repo.create_run(run_id=run_id, task_id=task_id, mode="offline", search_mode="branch_refine", max_run_usd=1.0)

    successes: List[int] = []
    rejections: List[int] = []

    def try_reserve(idx: int) -> None:
        op_id = k3_turso_manifest.record_operation(f"{prefix}op_{idx}")
        try:
            client.reserve_budget(
                run_id=run_id,
                operation_id=op_id,
                kind="model",
                estimated_usd=0.25,
                global_budget_usd=25.0,
            )
            successes.append(idx)
        except StorageConflictError:
            rejections.append(idx)

    import threading

    threads = [threading.Thread(target=try_reserve, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # With $1.00 run budget and $0.25 each, exactly 4 must succeed and 4 must be rejected
    assert len(successes) == 4
    assert len(rejections) == 4

    run = repo.get_run(run_id)
    assert run.usage.estimated_usd == 1.0

    usage = client.get_budget_usage()
    assert usage["reserved_micro_usd"] >= 1000000


def test_interrupted_run_recovery(k3_turso_client_and_repo, k3_turso_manifest):
    """Verify startup lifespan recovery transitions interrupted running tasks to failed."""
    client, repo, is_remote = k3_turso_client_and_repo
    prefix = k3_turso_manifest.prefix

    task_id = k3_turso_manifest.record_task(f"{prefix}task_rec")
    repo.upsert_task({
        "task_id": task_id,
        "title": "Recovery Task",
        "repository_url": "https://github.com/example/repo.git",
        "commit_sha": "abc1234",
        "dependency": "pkg",
        "from_version": "1.0",
        "to_version": "2.0",
    })

    run_id = k3_turso_manifest.record_run(f"{prefix}run_interrupted")
    repo.create_run(run_id=run_id, task_id=task_id, mode="offline", search_mode="sequential", state="running")

    # Simulate backend startup lifespan recovery with scoped prefix
    recover_interrupted_runs(repo=repo, acceptance_prefix=prefix)

    recovered = repo.get_run(run_id)
    assert recovered.state == "failed"
    assert "restarted" in (recovered.reason or "").lower()


@pytest.mark.asyncio
async def test_remote_acceptance_e2e_workflow(k3_turso_client_and_repo, k3_turso_manifest):
    """Verify complete end to end lifecycle against Turso persistence."""
    client, repo, is_remote = k3_turso_client_and_repo
    prefix = k3_turso_manifest.prefix

    task_id = k3_turso_manifest.record_task(f"{prefix}task_e2e")
    repo.upsert_task({
        "task_id": task_id,
        "title": "E2E Task",
        "repository_url": "https://github.com/example/repo.git",
        "commit_sha": "abc1234",
        "dependency": "sqlalchemy",
        "from_version": "1.4.48",
        "to_version": "2.0.19",
        "test_command": ["pytest"],
    })

    run_id = k3_turso_manifest.record_run(f"{prefix}run_e2e")
    repo.create_run(run_id=run_id, task_id=task_id, mode="offline", search_mode="sequential", max_run_usd=2.0)

    hp = TursoHostPorts(run_id=run_id, repo=repo)

    # 1. Start event
    await hp.emit("run.started", {
        "task_id": task_id, "mode": "offline", "search_mode": "sequential", "max_run_usd": 2.0,
    })

    # 2. Reserve budget
    k3_turso_manifest.record_operation(f"{run_id}:model:1")
    reserved = await hp.reserve("model:1", 0.05)
    assert reserved is True

    # 3. Baseline event
    await hp.emit("stage.completed", {"stage": "baseline", "passed": True, "summary": "Baseline clean"})

    # 4. Settle budget
    await hp.settle("model:1", 0.04)

    # 5. Store patch artifact
    patch_bytes = b"--- a/src/app.py\n+++ b/src/app.py\n@@ -1 +1 @@\n-old\n+new\n"
    art_id = k3_turso_manifest.record_artifact(await hp.save_artifact("patch", "patch.diff", patch_bytes))

    # 6. Verification completed event
    await hp.emit("stage.completed", {"stage": "verification", "passed": True, "summary": "Verified clean"})

    # 7. Finish run
    repo.finish_run(run_id, state="succeeded", reason="Repaired and verified")

    # Verify complete persisted state
    final_run = repo.get_run(run_id)
    assert final_run.state == "succeeded"
    assert len(final_run.artifacts) == 1
    assert final_run.artifacts[0].artifact_id == art_id

    events = repo.list_events(run_id)
    assert len(events) == 4
    assert [e.type for e in events] == ["run.started", "stage.completed", "stage.completed", "run.finished"]

    content = repo.get_artifact_content(run_id, art_id)
    assert content == patch_bytes


def test_concurrent_conflicting_settlement_cannot_overwrite(k3_turso_client_and_repo, k3_turso_manifest):
    """Verify concurrent conflicting settlements atomically commit exactly one amount."""
    client, repo, is_remote = k3_turso_client_and_repo
    prefix = k3_turso_manifest.prefix

    task_id = k3_turso_manifest.record_task(f"{prefix}task_settle_race")
    repo.upsert_task({
        "task_id": task_id,
        "title": "Settlement Race Task",
        "repository_url": "https://github.com/example/repo.git",
        "commit_sha": "abc1234",
        "dependency": "pkg",
        "from_version": "1.0",
        "to_version": "2.0",
    })

    run_id = k3_turso_manifest.record_run(f"{prefix}run_settle_race")
    repo.create_run(run_id=run_id, task_id=task_id, mode="offline", search_mode="sequential", max_run_usd=2.0)

    op_id = k3_turso_manifest.record_operation(f"{prefix}op_settle_race")
    client.reserve_budget(
        run_id=run_id,
        operation_id=op_id,
        kind="model",
        estimated_usd=0.50,
        global_budget_usd=25.0,
    )

    amounts = [0.10, 0.20, 0.30, 0.40]
    outcomes: dict[float, str] = {}
    lock = threading.Lock()

    def attempt_settle(amt: float) -> None:
        try:
            client.settle_budget(op_id, amt)
            with lock:
                outcomes[amt] = "success"
        except StorageConflictError as e:
            with lock:
                outcomes[amt] = f"conflict:{e.code}"
        except Exception as e:
            with lock:
                outcomes[amt] = f"error:{type(e).__name__}"

    threads = [threading.Thread(target=attempt_settle, args=(a,)) for a in amounts]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Exactly one amount succeeds, others receive conflict
    successes = [a for a, s in outcomes.items() if s == "success"]
    conflicts = [a for a, s in outcomes.items() if s.startswith("conflict")]
    assert len(successes) == 1
    assert len(conflicts) == len(amounts) - 1

    winning_amt = successes[0]
    losing_amt = conflicts[0]

    # Verify winning amount is committed
    cur = client._conn.execute(
        "SELECT settled_micro_usd, status FROM operations WHERE operation_id = ?",
        (op_id,),
    )
    row = cur.fetchone()
    assert row[1] == "settled"
    assert row[0] == int(winning_amt * 1_000_000)

    # Idempotent retry with winning amount succeeds
    retry_ok = client.settle_budget(op_id, winning_amt)
    assert retry_ok.get("ok") is True

    # Conflicting retry with losing amount fails
    with pytest.raises(StorageConflictError) as exc_info:
        client.settle_budget(op_id, losing_amt)
    assert exc_info.value.code == "operation_already_settled"


def test_actual_backend_process_termination_and_startup_recovery(k3_turso_client_and_repo, k3_turso_manifest):
    """Verify actual backend process SIGTERM termination and startup recovery against Turso."""
    client, repo, is_remote = k3_turso_client_and_repo
    prefix = f"{k3_turso_manifest.prefix}restart_"

    task_id = k3_turso_manifest.record_task(f"{prefix}task")
    repo.upsert_task({
        "task_id": task_id,
        "title": "Process Restart Task",
        "repository_url": "https://github.com/example/repo.git",
        "commit_sha": "abc1234",
        "dependency": "pkg",
        "from_version": "1.0",
        "to_version": "2.0",
    })

    # Step 1: Seed first interrupted run before backend launch
    seed_run_1 = k3_turso_manifest.record_run(f"{prefix}proc1")
    repo.create_run(
        run_id=seed_run_1,
        task_id=task_id,
        mode="offline",
        search_mode="sequential",
        state="running",
    )

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        test_port = s.getsockname()[1]

    backend_cwd = Path(__file__).resolve().parent.parent
    base_env = os.environ.copy()
    base_env["PORT"] = str(test_port)
    base_env["REPOMEDIC_STORAGE_BACKEND"] = "turso"
    base_env["TURSO_DATABASE_URL"] = client.database
    if client.auth_token:
        base_env["TURSO_AUTH_TOKEN"] = client.auth_token
    base_env["REPOMEDIC_MODE"] = "offline"
    base_env["REPOMEDIC_WORKER_ENABLED"] = "false"
    base_env["REPOMEDIC_ACCEPTANCE_PREFIX"] = prefix

    proc1: subprocess.Popen[bytes] | None = None
    proc2: subprocess.Popen[bytes] | None = None
    seed_run_2 = k3_turso_manifest.record_run(f"{prefix}proc2")

    def _wait_healthy(port: int, timeout_sec: float = 15.0) -> bool:
        start_t = time.time()
        while time.time() - start_t < timeout_sec:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/budget/usage", timeout=1.0) as resp:
                    if resp.status == 200:
                        return True
            except Exception:
                time.sleep(0.2)
        return False

    try:
        # Step 2: Spawn first backend process
        proc1 = subprocess.Popen(
            [
                "uv", "run", "python", "-m", "uvicorn", "src.main:create_app",
                "--factory", "--host", "127.0.0.1", "--port", str(test_port),
            ],
            cwd=str(backend_cwd),
            env=base_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        assert _wait_healthy(test_port), f"First backend process failed to become healthy on port {test_port}"

        # Step 3: Verify first run was recovered on backend startup
        run1 = repo.get_run(seed_run_1)
        assert run1.state == "failed", f"Expected seed_run_1 to be failed, got {run1.state}"
        assert "restarted" in (run1.reason or "").lower(), f"Expected restart reason, got {run1.reason}"

        # Step 4: Seed second run in running state while backend is active
        repo.create_run(
            run_id=seed_run_2,
            task_id=task_id,
            mode="offline",
            search_mode="branch_refine",
            state="running",
        )
        with urllib.request.urlopen(f"http://127.0.0.1:{test_port}/api/runs/{seed_run_2}", timeout=2.0) as resp:
            data = json.loads(resp.read().decode())
            assert data.get("state") == "running", f"Seed run 2 must be running initially, got {data.get('state')}"

        # Step 5: Terminate first backend process via SIGTERM
        proc1.terminate()
        proc1.wait(timeout=10)
        proc1 = None

        # Step 6: Verify second run remains running in storage while backend process is stopped
        run2_stopped = repo.get_run(seed_run_2)
        assert run2_stopped.state == "running", f"Seed run 2 must remain running while stopped, got {run2_stopped.state}"

        # Step 7: Restart backend process
        proc2 = subprocess.Popen(
            [
                "uv", "run", "python", "-m", "uvicorn", "src.main:create_app",
                "--factory", "--host", "127.0.0.1", "--port", str(test_port),
            ],
            cwd=str(backend_cwd),
            env=base_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        assert _wait_healthy(test_port), f"Restarted backend process failed to become healthy on port {test_port}"

        # Step 8: Verify second run is recovered upon process restart
        with urllib.request.urlopen(f"http://127.0.0.1:{test_port}/api/runs/{seed_run_2}", timeout=2.0) as resp:
            data = json.loads(resp.read().decode())
            assert data.get("state") == "failed", f"Expected seed_run_2 to be failed, got {data.get('state')}"
            assert "restarted" in (data.get("reason") or "").lower(), f"Expected restart reason, got {data.get('reason')}"

    except Exception as exc:
        artifacts_dir = backend_cwd.parent / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        failure_path = artifacts_dir / f"k3_proc_restart_failure_{int(time.time() * 1000)}.json"
        failure_info = {
            "test": "test_actual_backend_process_termination_and_startup_recovery",
            "is_remote": is_remote,
            "prefix": prefix,
            "seed_run_1": seed_run_1,
            "seed_run_2": seed_run_2,
            "error": str(exc),
            "proc1_stdout": proc1.stdout.read().decode(errors="replace") if proc1 and proc1.stdout else "",
            "proc1_stderr": proc1.stderr.read().decode(errors="replace") if proc1 and proc1.stderr else "",
            "proc2_stdout": proc2.stdout.read().decode(errors="replace") if proc2 and proc2.stdout else "",
            "proc2_stderr": proc2.stderr.read().decode(errors="replace") if proc2 and proc2.stderr else "",
        }
        failure_path.write_text(json.dumps(failure_info, indent=2), encoding="utf-8")
        raise
    finally:
        for p in (proc1, proc2):
            if p is not None and p.poll() is None:
                try:
                    p.terminate()
                    p.wait(timeout=5)
                except Exception:
                    p.kill()
