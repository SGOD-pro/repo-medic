import os
import subprocess
import tempfile
import pytest

from src.contracts import HostPorts, RepairRequest, TaskRecipe
from src.engine.adapters import CommandResult, SandboxPreset
from src.engine.candidate_generator import collect_target_source_files
from src.engine.fake_model import (
    DEMO_TASK_CANNED_PATCHES,
    FakeModelAdapter,
    JWT_VALID_PATCH,
    SHOP_VALID_PATCH,
    get_canned_patch_for_recipe,
)
from src.engine.fake_sandbox import FakeSandboxAdapter
from src.engine.patch_validator import validate_patch
from src.engine.repair import repair
from src.engine.upgrade import run_upgrade_stage


class InMemoryHost(HostPorts):
    def __init__(self):
        self.events = []
        self.reservations = {}
        self.is_cancelled = False

    async def emit(self, event_type: str, payload: dict) -> None:
        self.events.append({"type": event_type, "payload": payload})

    async def reserve(self, operation_id: str, amount_usd: float) -> bool:
        self.reservations[operation_id] = amount_usd
        return True

    async def settle(self, operation_id: str, amount_usd: float) -> None:
        self.reservations[operation_id] = amount_usd

    async def cancelled(self) -> bool:
        return self.is_cancelled


@pytest.mark.asyncio
async def test_offline_jwt_demo_repair():
    """Verify TASK-DEMO-JWT in offline mode generates patch for src/auth/tokens.py and succeeds cleanly."""
    recipe = TaskRecipe(
        task_id="TASK-DEMO-JWT",
        title="Upgrade pyjwt 1.7.1 to 2.8.0 in repomedic-demo-auth",
        repository_url="https://github.com/SGOD-pro/repo-medic.git",
        commit_sha="8b635e7ff84556962f6ec4fee43523778461c938",
        dependency="pyjwt",
        from_version="1.7.1",
        to_version="2.8.0",
        test_command=["pytest", "tests/"],
        allowed_source_paths=["src/auth/tokens.py"],
        expected_failure="AttributeError: 'str' object has no attribute 'decode'",
        timeout_seconds=60,
        max_candidates=3,
        max_refinements=1,
    )

    request = RepairRequest(
        run_id="run_jwt_test",
        task_id="TASK-DEMO-JWT",
        mode="offline",
        search_mode="sequential",
        max_run_usd=2.0,
    )

    host = InMemoryHost()
    result = await repair(request, recipe, host)

    assert result.state == "succeeded"
    # Verify candidate patch conforms to allowlist
    canned = get_canned_patch_for_recipe(recipe)
    assert canned is not None
    assert "src/auth/tokens.py" in canned
    assert "src/app.py" not in canned

    val = validate_patch(canned, recipe)
    assert val.valid is True


@pytest.mark.asyncio
async def test_unsupported_task_offline_fails_truthfully():
    """Verify an unknown custom task in offline mode fails with clear requirement for live mode."""
    recipe = TaskRecipe(
        task_id="TASK-CUSTOM-UNKNOWN",
        title="Custom repair: requests 2.25.0 to 2.28.0",
        repository_url="https://github.com/example/custom-repo.git",
        commit_sha="abcdef1234567890abcdef1234567890abcdef12",
        dependency="requests",
        from_version="2.25.0",
        to_version="2.28.0",
        test_command=["pytest", "tests/"],
        allowed_source_paths=["lib/client.py"],
        expected_failure="ImportError",
        timeout_seconds=60,
        max_candidates=3,
        max_refinements=1,
    )

    request = RepairRequest(
        run_id="run_unknown_offline",
        task_id="TASK-CUSTOM-UNKNOWN",
        mode="offline",
        search_mode="sequential",
        max_run_usd=2.0,
    )

    host = InMemoryHost()
    result = await repair(request, recipe, host)

    assert result.state == "failed"
    assert "Offline simulation does not support task" in result.reason
    assert "Live execution mode" in result.reason


@pytest.mark.asyncio
async def test_collect_target_source_files_resolves_directory_allowlist():
    """Verify collect_target_source_files resolves .py files under directory allowlists like src/shop/."""
    recipe = TaskRecipe(
        task_id="TASK-DIR-SHOP",
        title="Directory allowlist test",
        repository_url="https://github.com/SGOD-pro/repo-medic.git",
        commit_sha="8c400721558392a23b3af71766f673da02f80040",
        dependency="sqlalchemy",
        from_version="1.4.48",
        to_version="2.0.19",
        test_command=["pytest", "tests/"],
        allowed_source_paths=["src/shop/"],
        expected_failure="AttributeError: 'Engine' object has no attribute 'execute'",
        timeout_seconds=60,
        max_candidates=3,
        max_refinements=1,
    )

    error_output = (
        'Traceback (most recent call last):\n'
        '  File "/workspace/src/shop/database.py", line 10, in init_db\n'
        '    engine.execute(text("CREATE TABLE products"))\n'
        'AttributeError: \'Engine\' object has no attribute \'execute\''
    )

    sandbox = FakeSandboxAdapter()
    source_files = await collect_target_source_files(recipe, error_output, sandbox)

    assert "src/shop/database.py" in source_files
    assert "engine = create_engine" in source_files["src/shop/database.py"]


def test_patch_apply_against_pinned_shop_commit():
    """Verify clean patch applies to pinned shop commit and failed production patch reproduces failure."""
    actual_source = (
        'from sqlalchemy import create_engine, text\n\n'
        'engine = create_engine("sqlite:///:memory:")\n\n\n'
        'def init_db():\n'
        '    engine.execute(\n'
        '        text(\n'
        '            "CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT, price REAL, stock INTEGER)"\n'
        '        )\n'
        '    )\n'
        '    engine.execute(\n'
        '        text(\n'
        '            "INSERT INTO products (name, price, stock) VALUES (\'Espresso Mug\', 12.99, 50)"\n'
        '        )\n'
        '    )\n'
        '    engine.execute(\n'
        '        text(\n'
        '            "INSERT INTO products (name, price, stock) VALUES (\'Coffee Beans\', 18.50, 100)"\n'
        '        )\n'
        '    )\n\n\n'
        'def get_product_count():\n'
        '    res = engine.execute(text("SELECT count(*) FROM products"))\n'
        '    return res.scalar()\n\n\n'
        'def get_product(product_id: int):\n'
        '    res = engine.execute(\n'
        '        text("SELECT id, name, price, stock FROM products WHERE id = :id"),\n'
        '        {"id": product_id},\n'
        '    )\n'
        '    row = res.fetchone()\n'
        '    if row:\n'
        '        return {"id": row[0], "name": row[1], "price": row[2], "stock": row[3]}\n'
        '    return None\n'
    )

    failed_production_patch = (
        '--- a/src/shop/database.py\n'
        '+++ b/src/shop/database.py\n'
        '@@ -4,7 +4,9 @@\n'
        ' from sqlalchemy import text\n'
        ' \n'
        ' def init_db():\n'
        '-    engine = create_engine("sqlite:///./test.db")\n'
        '-    engine.execute(\n'
        '-        text("CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT, price REAL, stock INTEGER)")\n'
        '-    )\n'
        '+    engine = create_engine("sqlite:///./test.db")\n'
        '+    with engine.begin() as conn:\n'
        '+        conn.execute(text("CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT, price REAL, stock INTEGER)"))\n'
        '+\n'
        ' if __name__ == "__main__":\n'
        '     init_db()\n'
    )

    with tempfile.TemporaryDirectory() as td:
        subprocess.check_call(["git", "init"], cwd=td)
        subprocess.check_call(["git", "config", "user.name", "Tester"], cwd=td)
        subprocess.check_call(["git", "config", "user.email", "test@repomedic.io"], cwd=td)
        os.makedirs(os.path.join(td, "src/shop"), exist_ok=True)
        with open(os.path.join(td, "src/shop/database.py"), "w", encoding="utf-8") as f:
            f.write(actual_source)
        subprocess.check_call(["git", "add", "."], cwd=td)
        subprocess.check_call(["git", "commit", "-m", "init"], cwd=td)

        # 1. Test failed production patch fails with exact diagnostic
        with open(os.path.join(td, "failed.patch"), "w", encoding="utf-8") as f:
            f.write(failed_production_patch)
        res_fail = subprocess.run(
            ["git", "apply", "--recount", "--unidiff-zero", "--whitespace=nowarn", "failed.patch"],
            cwd=td,
            capture_output=True,
            text=True,
        )
        assert res_fail.returncode == 1
        assert "error: patch failed: src/shop/database.py:4" in res_fail.stderr
        assert "patch does not apply" in res_fail.stderr

        # 2. Test valid patch applies cleanly
        with open(os.path.join(td, "valid.patch"), "w", encoding="utf-8") as f:
            f.write(SHOP_VALID_PATCH)
        res_ok = subprocess.run(
            ["git", "apply", "--recount", "--unidiff-zero", "--whitespace=nowarn", "valid.patch"],
            cwd=td,
            capture_output=True,
            text=True,
        )
        assert res_ok.returncode == 0


@pytest.mark.asyncio
async def test_automatic_regression_discovery_no_failure():
    """Verify that when expected_failure is omitted and tests pass under target version, clean success is returned."""
    recipe = TaskRecipe(
        task_id="TASK-CLEAN-UPGRADE",
        title="Clean upgrade without regressions",
        repository_url="https://github.com/SGOD-pro/repo-medic.git",
        commit_sha="8c400721558392a23b3af71766f673da02f80040",
        dependency="urllib3",
        from_version="1.26.5",
        to_version="1.26.6",
        test_command=["pytest", "tests/"],
        allowed_source_paths=["src/"],
        expected_failure=None,
        timeout_seconds=60,
        max_candidates=3,
        max_refinements=1,
    )

    host = InMemoryHost()
    # Sandbox where upgrade test execution passes (UPGRADE_FAILURE_NOT_REPRODUCED returns exit_code=0)
    sandbox = FakeSandboxAdapter(preset=SandboxPreset.UPGRADE_FAILURE_NOT_REPRODUCED)
    upgrade_res = await run_upgrade_stage(recipe, sandbox, host)

    assert upgrade_res.success is True
    assert upgrade_res.no_regression_detected is True
    assert "No regression detected" in upgrade_res.summary

    request = RepairRequest(
        run_id="run_clean_upgrade",
        task_id="TASK-CLEAN-UPGRADE",
        mode="offline",
        search_mode="sequential",
        max_run_usd=2.0,
    )
    result = await repair(request, recipe, host, sandbox=sandbox)
    assert result.state == "succeeded"
    assert "No regression detected" in result.reason


@pytest.mark.asyncio
async def test_automatic_regression_discovery_with_failure():
    """Verify that when expected_failure is omitted and tests fail under target version, failure is captured for repair."""
    recipe = TaskRecipe(
        task_id="TASK-REGRESSION-UPGRADE",
        title="Upgrade with regression",
        repository_url="https://github.com/SGOD-pro/repo-medic.git",
        commit_sha="8c400721558392a23b3af71766f673da02f80040",
        dependency="sqlalchemy",
        from_version="1.4.48",
        to_version="2.0.19",
        test_command=["pytest", "tests/"],
        allowed_source_paths=["src/"],
        expected_failure=None,
        timeout_seconds=60,
        max_candidates=3,
        max_refinements=1,
    )

    host = InMemoryHost()
    sandbox = FakeSandboxAdapter(reproduced_failure_stderr="AttributeError: Engine has no execute")
    upgrade_res = await run_upgrade_stage(recipe, sandbox, host)

    assert upgrade_res.success is True
    assert upgrade_res.failure_reproduced is True
    assert "captured test regression automatically" in upgrade_res.summary
