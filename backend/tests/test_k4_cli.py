import os
import subprocess
import sys
from pathlib import Path
import pytest

from src.contracts import TaskRecipe
from src.engine.candidate import CandidatePatch
from src.engine.verifier import verify_candidate_patch
from src.preflight import verify_live_providers
from src.storage.fake_host import FakeHost

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from run_live_sequential_repair import sanitize_text  # noqa: E402


def test_preflight_cli_live_providers_output():
    """covers: AC-13 - CLI preflight --live-providers exits zero and reports provider status."""
    cmd = [sys.executable, str(SCRIPTS_DIR / "preflight_check.py"), "--live-providers"]
    res = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True)
    assert res.returncode == 0
    assert "Live Provider Inspection" in res.stdout
    assert "token_factory_api_key" in res.stdout
    assert "nebius_sandbox_image" in res.stdout
    assert "All live provider preflight checks passed" in res.stdout


def test_preflight_cli_missing_credentials_fails():
    """covers: AC-1, AC-13 - Preflight CLI fails closed when credentials are wiped."""
    env = dict(os.environ)
    env["TOKEN_FACTORY_API_KEY"] = ""
    env["NEBIUS_API_KEY"] = ""
    env["NEBIUS_PROJECT_ID"] = ""

    cmd = [sys.executable, str(SCRIPTS_DIR / "preflight_check.py"), "--live-providers"]
    res = subprocess.run(cmd, cwd=str(REPO_ROOT), env=env, capture_output=True, text=True)
    assert res.returncode == 1
    assert "[FAIL]" in res.stdout


def test_run_live_sequential_repair_dry_run_cli():
    """covers: AC-1..AC-12 - Sequential repair CLI dry-run executes cleanly with default task recipe."""
    cmd = [sys.executable, str(SCRIPTS_DIR / "run_live_sequential_repair.py"), "--dry-run"]
    res = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True)
    assert res.returncode == 0
    assert "Dry run mode active" in res.stdout
    assert "TASK-091" in res.stdout
    assert "Search mode: sequential" in res.stdout


def test_runner_resolves_task_093_branch_refine_search_mode():
    """Verify that TASK-093 automatically resolves search_mode=branch_refine through the runner."""
    recipe_path = REPO_ROOT / "fixtures" / "tasks" / "TASK-093.json"
    cmd = [
        sys.executable,
        str(SCRIPTS_DIR / "run_live_sequential_repair.py"),
        "--dry-run",
        "--recipe",
        str(recipe_path),
    ]
    res = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True)
    assert res.returncode == 0
    assert "TASK-093" in res.stdout
    assert "Search mode: branch_refine" in res.stdout


def test_runner_resolves_task_092_sequential_search_mode():
    """Verify that TASK-092 resolves search_mode=sequential through the runner."""
    recipe_path = REPO_ROOT / "fixtures" / "tasks" / "TASK-092.json"
    cmd = [
        sys.executable,
        str(SCRIPTS_DIR / "run_live_sequential_repair.py"),
        "--dry-run",
        "--recipe",
        str(recipe_path),
    ]
    res = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True)
    assert res.returncode == 0
    assert "TASK-092" in res.stdout
    assert "Search mode: sequential" in res.stdout


def test_runner_explicit_search_mode_override():
    """Verify that CLI --search-mode override takes precedence."""
    cmd = [
        sys.executable,
        str(SCRIPTS_DIR / "run_live_sequential_repair.py"),
        "--dry-run",
        "--search-mode",
        "branch_refine",
    ]
    res = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True)
    assert res.returncode == 0
    assert "Search mode: branch_refine" in res.stdout


def test_preflight_spending_limits_enforced():
    """covers: AC-10 - Confirms preflight rejects limits exceeding spending and time bounds."""
    res_high_run = verify_live_providers(max_run_usd=5.0)
    assert res_high_run.passed is False
    assert any("not exceed 2.00 USD" in err for err in res_high_run.errors)

    res_high_global = verify_live_providers(total_budget_usd=50.0)
    assert res_high_global.passed is False
    assert any("not exceed 25.00 USD" in err for err in res_high_global.errors)

    res_high_timeout = verify_live_providers(timeout_seconds=900)
    assert res_high_timeout.passed is False
    assert any("not exceed 600 seconds" in err for err in res_high_timeout.errors)


def test_preflight_inaccessible_repository_fails():
    """covers: AC-3 - Confirms preflight rejects inaccessible git repository URLs."""
    res = verify_live_providers(
        repository_url="https://github.com/nonexistent-org-12345/nonexistent-repo-999.git"
    )
    assert res.passed is False
    assert any("is not accessible" in err for err in res.errors)


def test_sanitize_text_redacts_credentials():
    """covers: AC-1 - Confirms secret strings are properly sanitized from log records."""
    secret_key = "secret_nebius_token_123456"
    log_line = f"Connecting to provider using authorization Bearer {secret_key} on project"
    sanitized = sanitize_text(log_line, [secret_key])
    assert secret_key not in sanitized
    assert "***REDACTED***" in sanitized


def test_preflight_cli_with_repository_flags():
    """covers: AC-3, AC-13 - Confirms CLI preflight validates public repository and commit SHA."""
    cmd = [
        sys.executable,
        str(SCRIPTS_DIR / "preflight_check.py"),
        "--live-providers",
        "--repository-url",
        "https://github.com/SGOD-pro/repo-medic.git",
        "--commit-sha",
        "453a0b6c6b125177504cdd941902b8d48266ed1c",
    ]
    res = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True)
    assert res.returncode == 0
    assert "repository_access" in res.stdout
    assert "All live provider preflight checks passed" in res.stdout


def test_run_live_sequential_repair_custom_recipe_flag():
    """covers: AC-1..AC-12 - Confirms runner accepts custom recipe path via CLI."""
    recipe_path = REPO_ROOT / "fixtures" / "tasks" / "TASK-091.json"
    cmd = [
        sys.executable,
        str(SCRIPTS_DIR / "run_live_sequential_repair.py"),
        "--dry-run",
        "--recipe",
        str(recipe_path),
    ]
    res = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True)
    assert res.returncode == 0
    assert "Dry run mode active" in res.stdout
    assert "TASK-091" in res.stdout


@pytest.mark.asyncio
async def test_run_live_failure_saves_sanitized_record(monkeypatch, tmp_path):
    """covers: AC-1, AC-12 - Confirms failure path saves sanitized failure artifact and returns exit code 1."""
    from run_live_sequential_repair import run_live
    from src.preflight import PreflightResult
    from src.storage.db_client import RepoMedicDB
    from src.storage.repository import D1StorageRepository
    from tests.test_storage import create_sqlite_d1_transport

    # Mock preflight to pass
    monkeypatch.setattr(
        "run_live_sequential_repair.verify_live_providers",
        lambda **kwargs: PreflightResult(passed=True, checks=[], errors=[]),
    )

    # Use in memory SQLite repo
    token = "dev-token"
    transport = create_sqlite_d1_transport(expected_token=token)
    db = RepoMedicDB(base_url="http://test-bridge", api_key=token, transport=transport)
    test_repo = D1StorageRepository(db)
    monkeypatch.setattr("run_live_sequential_repair.get_d1_repository", lambda: test_repo)

    # Mock QueueWorker to simulate failed run
    async def mock_process_one(self):
        self.repo.update_run_state(self.acceptance_prefix, state="running", from_state="queued")
        secret = "secret_nebius_key_token_999"
        self.repo.finish_run(self.acceptance_prefix, state="failed", reason=f"Failure with token {secret}")
        return True

    monkeypatch.setattr("run_live_sequential_repair.QueueWorker.process_one", mock_process_one)
    monkeypatch.setenv("NEBIUS_API_KEY", "secret_nebius_key_token_999")

    recipe = TaskRecipe(
        task_id="TASK-091",
        title="Test Task",
        repository_url="https://github.com/SGOD-pro/repo-medic.git",
        commit_sha="453a0b6c6b125177504cdd941902b8d48266ed1c",
        dependency="dep",
        from_version="1.0",
        to_version="2.0",
        test_command=["pytest", "tests/"],
        allowed_source_paths=["src/"],
        expected_failure="Error",
        timeout_seconds=60,
        max_candidates=1,
        max_refinements=0,
    )

    run_id = f"test_fail_run_{tmp_path.name}"
    exit_code = await run_live(recipe, dry_run=False, run_id_override=run_id)
    assert exit_code == 1

    # Verify failure artifact was written to disk and token is sanitized
    failure_files = list((REPO_ROOT / "artifacts").glob("live_repair_failure_*.json"))
    assert len(failure_files) > 0
    latest_failure = max(failure_files, key=lambda p: p.stat().st_mtime)
    content = latest_failure.read_text(encoding="utf-8")
    assert "secret_nebius_key_token_999" not in content
    assert "***REDACTED***" in content

    # Cleanup test failure file
    latest_failure.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_verifier_finally_settles_budget_on_creation_failure():
    """covers: AC-10 - Confirms host.settle is called even when create_execution fails."""
    host = FakeHost()
    candidate = CandidatePatch(
        candidate_id="cand_fail_setup",
        diff_content="--- a/src/app.py\n+++ b/src/app.py\n@@ -1 +1 @@\n-1\n+2\n",
        modified_files=["src/app.py"],
    )
    recipe = TaskRecipe(
        task_id="TASK-091",
        title="Test Task",
        repository_url="https://example.com/repo",
        commit_sha="abcdef",
        dependency="dep",
        from_version="1.0",
        to_version="2.0",
        test_command=["pytest", "tests/"],
        allowed_source_paths=["src/"],
        expected_failure="Error",
        timeout_seconds=60,
        max_candidates=1,
        max_refinements=0,
    )

    class BrokenSandbox:
        async def create_execution(self, checkpoint_id: str):
            raise RuntimeError("Cloud provider capacity exceeded")

    sandbox = BrokenSandbox()

    result = await verify_candidate_patch(
        candidate=candidate,
        recipe=recipe,
        sandbox=sandbox,
        host=host,
        baseline_collected_count=2,
        baseline_preservation=None,
        checkpoint_id="chk_abc",
        mode="live",
    )

    assert result.passed is False
    assert result.reason == "execution_creation_failed"
    # Ensure 0.10 reservation was settled via finally block without leaking
    op_id = f"sandbox:verify:{candidate.candidate_id}"
    assert op_id in host.settlements
    assert host.settlements[op_id] == 0.10
