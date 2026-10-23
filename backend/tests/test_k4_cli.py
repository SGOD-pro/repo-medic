import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
import pytest

from src.contracts import TaskRecipe
from src.engine.candidate import CandidatePatch, VerificationChecks
from src.engine.verifier import verify_candidate_patch
from src.storage.fake_host import FakeHost


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"


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
