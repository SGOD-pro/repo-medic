import json
import os
import subprocess
import tempfile
from pathlib import Path
import pytest

from src.contracts import HostPorts, RepairRequest, TaskRecipe
from src.engine.adapters import CommandResult, SandboxPreset
from src.engine.baseline import run_baseline_stage
from src.engine.candidate_generator import (
    collect_target_source_files,
    normalize_diff_context,
)
from src.engine.fake_model import (
    DEFAULT_VALID_PATCH,
    DEMO_TASK_CANNED_PATCHES,
    FakeModelAdapter,
    JWT_VALID_PATCH,
    SHOP_VALID_PATCH,
    UNSAFE_TEST_PATCH,
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


def test_jwt_candidate_allowlist_rejection():
    """Verify production error: candidate proposing src/app.py is rejected against JWT allowed_source_paths."""
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

    # DEFAULT_VALID_PATCH modifies src/app.py
    res = validate_patch(DEFAULT_VALID_PATCH, recipe)
    assert res.valid is False
    assert any("File 'src/app.py' is outside recipe allowed source paths" in v for v in res.violations)
    assert "Patch safety validation failed" in res.reason


@pytest.mark.asyncio
async def test_known_error_match_and_mismatch():
    """Verify known error reproduction matches and reports clear diagnostic on mismatch."""
    recipe = TaskRecipe(
        task_id="TASK-MATCH-TEST",
        title="Known error test",
        repository_url="https://github.com/SGOD-pro/repo-medic.git",
        commit_sha="8c400721558392a23b3af71766f673da02f80040",
        dependency="sqlalchemy",
        from_version="1.4.48",
        to_version="2.0.19",
        test_command=["pytest", "tests/"],
        allowed_source_paths=["src/"],
        expected_failure="AttributeError: Engine has no execute",
        timeout_seconds=60,
        max_candidates=3,
        max_refinements=1,
    )

    # 1. Matching failure
    host_match = InMemoryHost()
    sandbox_match = FakeSandboxAdapter(reproduced_failure_stderr="AttributeError: Engine has no execute")
    res_match = await run_upgrade_stage(recipe, sandbox_match, host_match)
    assert res_match.success is True
    assert res_match.failure_reproduced is True

    # 2. Mismatching failure
    recipe_mismatch = recipe.model_copy(update={"expected_failure": "CustomMismatchPatternExpected"})
    host_mismatch = InMemoryHost()
    sandbox_mismatch = FakeSandboxAdapter(reproduced_failure_stderr="AttributeError: Engine has no execute")
    res_mismatch = await run_upgrade_stage(recipe_mismatch, sandbox_mismatch, host_mismatch)
    assert res_mismatch.success is False
    assert res_mismatch.failure_reproduced is False
    assert "CustomMismatchPatternExpected' was not observed" in res_mismatch.summary


@pytest.mark.asyncio
async def test_automatic_discovery_empty_baseline():
    """Verify automatic regression discovery fails baseline when 0 tests are collected."""
    recipe = TaskRecipe(
        task_id="TASK-EMPTY-BASELINE",
        title="Empty baseline test",
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
    sandbox = FakeSandboxAdapter()
    sandbox.node_ids = []  # 0 collected tests

    baseline_res = await run_baseline_stage(recipe, sandbox, host)
    assert baseline_res.passed is False
    assert "Baseline test collection empty: 0 tests collected" in baseline_res.summary


@pytest.mark.asyncio
async def test_automatic_discovery_install_failure():
    """Verify dependency upgrade install failure is distinguished from regression and preserved."""
    recipe = TaskRecipe(
        task_id="TASK-INSTALL-FAIL",
        title="Install failure test",
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
    sandbox = FakeSandboxAdapter(preset=SandboxPreset.UPGRADE_INSTALL_FAIL)
    upgrade_res = await run_upgrade_stage(recipe, sandbox, host)

    assert upgrade_res.success is False
    assert "Package upgrade command failed" in upgrade_res.summary


@pytest.mark.asyncio
async def test_automatic_discovery_collection_failure():
    """Verify post-upgrade collection failure (exit code 5) is distinguished from test regression."""
    recipe = TaskRecipe(
        task_id="TASK-COLLECTION-FAIL",
        title="Collection failure test",
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
    sandbox = FakeSandboxAdapter()

    # Override execute_command to return exit code 5 (Pytest collection error)
    orig_exec = sandbox.execute_command

    async def mock_exec(cmd, **kwargs):
        if cmd == recipe.test_command:
            return CommandResult(
                exit_code=5,
                stdout="ERROR collecting tests/test_broken.py\nImportError: No module named broken",
                stderr="",
            )
        return await orig_exec(cmd, **kwargs)

    sandbox.execute_command = mock_exec
    upgrade_res = await run_upgrade_stage(recipe, sandbox, host)

    assert upgrade_res.success is False
    assert "Post-upgrade test collection failed under 2.0.19 (exit code 5)" in upgrade_res.summary


@pytest.mark.asyncio
async def test_automatic_discovery_timeout_failure():
    """Verify test execution timeout failure is caught and preserved with clear diagnostic."""
    recipe = TaskRecipe(
        task_id="TASK-TIMEOUT-FAIL",
        title="Timeout failure test",
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
    sandbox = FakeSandboxAdapter()

    orig_exec = sandbox.execute_command

    async def mock_timeout(cmd, **kwargs):
        if cmd == recipe.test_command:
            raise TimeoutError("Test execution exceeded 60s timeout ceiling")
        return await orig_exec(cmd, **kwargs)

    sandbox.execute_command = mock_timeout
    upgrade_res = await run_upgrade_stage(recipe, sandbox, host)

    assert upgrade_res.success is False
    assert "Post-upgrade test execution timed out" in upgrade_res.summary


def test_unchanged_test_verification():
    """Verify candidate patch attempting to modify test files is strictly rejected."""
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

    res = validate_patch(UNSAFE_TEST_PATCH, recipe)
    assert res.valid is False
    assert any("not permitted: tests/test_app.py" in v for v in res.violations)
    assert "Patch safety validation failed" in res.reason


def test_all_canned_demo_task_recipes_offline_compatibility():
    """Verify all curated demo task recipes have valid canned patches matching their allowed source paths."""
    fixtures_dir = Path(__file__).resolve().parent.parent / "fixtures" / "tasks"
    demo_tasks = ["TASK-DEMO-JWT", "TASK-DEMO-SHOP", "TASK-DEMO-CLICK", "TASK-DEMO-PYDANTIC"]

    for task_id in demo_tasks:
        fixture_path = fixtures_dir / f"{task_id}.json"
        assert fixture_path.exists(), f"Missing fixture file for {task_id}"
        with open(fixture_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        recipe = TaskRecipe(**data)

        canned = get_canned_patch_for_recipe(recipe)
        assert canned is not None, f"Canned patch missing for {task_id}"
        val = validate_patch(canned, recipe)
        assert val.valid is True, f"Canned patch for {task_id} failed validation: {val.violations}"


def test_actual_production_patch_apply_regression(tmp_path):
    """Reproduce the exact production patch failure from run_05ff3b08a62b49b98a69cabb7573ed37 and verify clean application."""
    diff_path = (
        Path(__file__).resolve().parent.parent.parent
        / "artifacts"
        / "run_05ff3b08a62b49b98a69cabb7573ed37"
        / "patch.diff"
    )
    assert diff_path.exists(), f"Saved patch artifact missing at {diff_path}"
    raw_diff = diff_path.read_text(encoding="utf-8")

    # Pinned commit source for src/shop/database.py at 8c400721558392a23b3af71766f673da02f80040
    src_content = subprocess.check_output(
        ["git", "cat-file", "-p", "8c400721558392a23b3af71766f673da02f80040:src/shop/database.py"]
    ).decode("utf-8")

    # Set up clean temporary git repository matching the pinned commit
    repo_dir = tmp_path / "repo_prod_patch"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=str(repo_dir), check=True, capture_output=True)
    shop_dir = repo_dir / "src" / "shop"
    shop_dir.mkdir(parents=True)
    db_file = shop_dir / "database.py"
    db_file.write_text(src_content, encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=str(repo_dir), check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.name=RepoMedic", "-c", "user.email=ci@repo-medic.local", "commit", "-m", "init"],
        cwd=str(repo_dir),
        check=True,
        capture_output=True,
    )

    # 1. Verify un-normalized raw diff fails git apply with the exact error observed in production
    raw_apply = subprocess.run(
        ["git", "apply", "--check", "-v", "--recount", "--unidiff-zero", "--whitespace=nowarn"],
        cwd=str(repo_dir),
        input=raw_diff,
        text=True,
        capture_output=True,
    )
    assert raw_apply.returncode != 0
    assert "patch failed: src/shop/database.py:6" in raw_apply.stderr
    assert "patch does not apply" in raw_apply.stderr

    # 2. Normalize diff using authentic source lines
    source_files = {"src/shop/database.py": src_content}
    normalized_diff = normalize_diff_context(raw_diff, source_files=source_files)
    assert normalized_diff != raw_diff

    # 3. Verify normalized diff applies cleanly
    norm_apply = subprocess.run(
        ["git", "apply", "--check", "-v", "--recount", "--unidiff-zero", "--whitespace=nowarn"],
        cwd=str(repo_dir),
        input=normalized_diff,
        text=True,
        capture_output=True,
    )
    assert norm_apply.returncode == 0
    assert "Checking patch src/shop/database.py..." in norm_apply.stderr

    # 4. Apply the patch and verify content
    subprocess.run(
        ["git", "apply", "--recount", "--unidiff-zero", "--whitespace=nowarn"],
        cwd=str(repo_dir),
        input=normalized_diff,
        text=True,
        check=True,
    )
    updated_source = db_file.read_text(encoding="utf-8")
    assert "with engine.begin() as conn:" in updated_source
    assert "with engine.connect() as conn:" in updated_source


def test_ambiguous_patch_rejected_without_guessing():
    """Verify hunks matching multiple locations ambiguously are rejected without guessing."""
    source_text = (
        "def compute_alpha():\n"
        "    return None\n"
        "\n"
        "def compute_beta():\n"
        "    return None\n"
    )
    ambiguous_diff = (
        "--- a/src/calc.py\n"
        "+++ b/src/calc.py\n"
        "@@ -2,1 +2,1 @@\n"
        "-    return None\n"
        "+    return 42\n"
    )
    source_files = {"src/calc.py": source_text}
    result = normalize_diff_context(ambiguous_diff, source_files=source_files)
    assert result.strip() == ambiguous_diff.strip()


def test_mismatched_patch_fails_clearly(tmp_path):
    """Verify mismatched patch fails git apply clearly and does not corrupt source."""
    source_text = "def greet(name: str) -> str:\n    return f'Hello {name}'\n"
    mismatched_diff = (
        "--- a/src/greet.py\n"
        "+++ b/src/greet.py\n"
        "@@ -1,2 +1,2 @@\n"
        "-def goodbye(name: str) -> str:\n"
        "-    return f'Bye {name}'\n"
        "+def farewell(name: str) -> str:\n"
        "+    return f'Farewell {name}'\n"
    )
    repo_dir = tmp_path / "repo_mismatch"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=str(repo_dir), check=True, capture_output=True)
    src_dir = repo_dir / "src"
    src_dir.mkdir(parents=True)
    greet_file = src_dir / "greet.py"
    greet_file.write_text(source_text, encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=str(repo_dir), check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.name=RepoMedic", "-c", "user.email=ci@repo-medic.local", "commit", "-m", "init"],
        cwd=str(repo_dir),
        check=True,
        capture_output=True,
    )

    source_files = {"src/greet.py": source_text}
    normalized = normalize_diff_context(mismatched_diff, source_files=source_files)
    res = subprocess.run(
        ["git", "apply", "--check", "-v", "--recount", "--unidiff-zero", "--whitespace=nowarn"],
        cwd=str(repo_dir),
        input=normalized,
        text=True,
        capture_output=True,
    )
    assert res.returncode != 0
    assert "patch failed: src/greet.py:1" in res.stderr
    assert greet_file.read_text(encoding="utf-8") == source_text


@pytest.mark.asyncio
async def test_repair_emits_repair_stage_completed_event():
    """Verify repair stage emits stage.completed with stage: repair when candidate is generated."""
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
        run_id="run_repair_event_test",
        task_id="TASK-DEMO-JWT",
        mode="offline",
        search_mode="sequential",
        max_run_usd=2.0,
    )

    host = InMemoryHost()
    result = await repair(request, recipe, host)

    assert result.state == "succeeded"
    repair_events = [
        e
        for e in host.events
        if e.get("type") == "stage.completed"
        and e.get("payload", {}).get("stage") == "repair"
    ]
    assert len(repair_events) == 1
    assert repair_events[0]["payload"]["passed"] is True


