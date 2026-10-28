import pytest
from src.contracts import RepairRequest, TaskRecipe
from src.engine.adapters import SandboxPreset
from src.engine.candidate import CandidatePatch, UpgradeResult
from src.engine.candidate_generator import (
    BudgetExceededError,
    build_repair_prompt,
    generate_candidate_patch,
)
from src.engine.extraction import extract_error_context
from src.engine.fake_model import FakeModelAdapter, UNSAFE_TEST_PATCH, UNSAFE_TRAVERSAL_PATCH
from src.engine.fake_sandbox import FakeSandboxAdapter
from src.engine.patch_validator import parse_modified_files, validate_patch
from src.engine.repair import repair
from src.engine.upgrade import derive_upgrade_command, run_upgrade_stage
from src.engine.verifier import verify_candidate_patch
from src.storage.fake_host import FakeHost


@pytest.fixture
def sample_recipe() -> TaskRecipe:
    return TaskRecipe(
        task_id="test-task-1",
        title="Upgrade mock library from 1.0.0 to 2.0.0",
        repository_url="https://github.com/example/repo",
        commit_sha="123456abcdef",
        dependency="example-lib",
        from_version="1.0.0",
        to_version="2.0.0",
        test_command=["pytest", "tests/"],
        allowed_source_paths=["src/"],
        expected_failure="AssertionError",
        timeout_seconds=60,
        max_candidates=1,
        max_refinements=0,
    )


@pytest.fixture
def sample_request() -> RepairRequest:
    return RepairRequest(
        run_id="run-1",
        task_id="test-task-1",
        mode="offline",
        search_mode="sequential",
        max_run_usd=1.0,
    )


# --- AC-1: Baseline Precondition ---
@pytest.mark.asyncio
async def test_sequential_repair_halts_on_baseline_failure(
    sample_request: RepairRequest, sample_recipe: TaskRecipe
):
    host = FakeHost()
    sandbox = FakeSandboxAdapter(preset=SandboxPreset.FIRST_FAIL)
    result = await repair(sample_request, sample_recipe, host, sandbox=sandbox)

    assert result.state == "failed"
    assert "Baseline check 1 failed" in (result.reason or "")
    # Should not have attempted upgrade
    assert not any(cmd[0] == "pip" for cmd in sandbox.executed_commands)


# --- AC-2 & AC-3: Upgrade Execution and Failure Reproduction ---
def test_derive_upgrade_command():
    cmd = derive_upgrade_command("pytest-mock", "3.11.1")
    assert cmd == ["pip", "install", "pytest-mock==3.11.1"]


@pytest.mark.asyncio
async def test_upgrade_stage_success(sample_recipe: TaskRecipe):
    host = FakeHost()
    sandbox = FakeSandboxAdapter(preset=SandboxPreset.SUCCESS)
    sandbox._upgrade_installed = False

    upgrade_res = await run_upgrade_stage(sample_recipe, sandbox, host)
    assert upgrade_res.success is True
    assert upgrade_res.failure_reproduced is True
    assert "AssertionError" in upgrade_res.failure_output

    events = [e for e in host.events if e["type"] == "stage.completed"]
    assert any(
        e["payload"].get("stage") == "upgrade" and e["payload"].get("passed") is True
        for e in events
    )


@pytest.mark.asyncio
async def test_upgrade_stage_install_failure(sample_recipe: TaskRecipe):
    host = FakeHost()
    sandbox = FakeSandboxAdapter(preset=SandboxPreset.UPGRADE_INSTALL_FAIL)

    upgrade_res = await run_upgrade_stage(sample_recipe, sandbox, host)
    assert upgrade_res.success is False
    assert "Package upgrade command failed" in upgrade_res.summary

    events = [e for e in host.events if e["type"] == "stage.completed"]
    assert any(
        e["payload"].get("stage") == "upgrade" and e["payload"].get("passed") is False
        for e in events
    )


@pytest.mark.asyncio
async def test_upgrade_stage_failure_not_reproduced(sample_recipe: TaskRecipe):
    host = FakeHost()
    sandbox = FakeSandboxAdapter(preset=SandboxPreset.UPGRADE_FAILURE_NOT_REPRODUCED)

    upgrade_res = await run_upgrade_stage(sample_recipe, sandbox, host)
    assert upgrade_res.success is False
    assert upgrade_res.failure_reproduced is False
    assert "passed cleanly" in upgrade_res.summary


@pytest.mark.asyncio
async def test_upgrade_stage_unexpected_failure(sample_recipe: TaskRecipe):
    host = FakeHost()
    sandbox = FakeSandboxAdapter(preset=SandboxPreset.UPGRADE_UNEXPECTED_FAILURE)

    upgrade_res = await run_upgrade_stage(sample_recipe, sandbox, host)
    assert upgrade_res.success is False
    assert upgrade_res.failure_reproduced is False
    assert "expected failure pattern" in upgrade_res.summary


# --- AC-4: Regex Error Extraction and Fallback ---
def test_extract_error_context_traceback():
    log = """
running tests...
Traceback (most recent call last):
  File "src/app.py", line 42, in run
    assert val == 2
AssertionError: Expected 2 got 1
==================== 1 failed in 0.1s ====================
"""
    error_block, files = extract_error_context(log)
    assert "AssertionError" in error_block
    assert "src/app.py" in files


def test_extract_error_context_pytest_summary():
    log = """
FAILED tests/test_app.py::test_bar - AssertionError: broken
"""
    error_block, files = extract_error_context(log)
    assert "FAILED tests/test_app.py" in error_block
    assert "tests/test_app.py" in files


def test_extract_error_context_fallback():
    raw_log = "Error occurred somewhere without standard traceback lines\n" * 5
    error_block, files = extract_error_context(raw_log)
    assert "Error occurred somewhere" in error_block


# --- AC-5 & AC-6: Prompt Construction and Budget Reservations ---
def test_build_repair_prompt(sample_recipe: TaskRecipe):
    up = UpgradeResult(success=True, failure_output="AssertionError: mock failed")
    prompt = build_repair_prompt(sample_recipe, up, "AssertionError: mock failed", ["src/app.py"])
    assert "example-lib" in prompt
    assert "2.0.0" in prompt
    assert "src/app.py" in prompt
    assert "--- Observed failure after upgrade ---" in prompt


@pytest.mark.asyncio
async def test_candidate_generation_budget_reservation(sample_recipe: TaskRecipe):
    host = FakeHost()

    async def deny_reserve(op_id: str, amt: float) -> bool:
        return False

    host.reserve = deny_reserve  # type: ignore
    model = FakeModelAdapter()
    up = UpgradeResult(success=True, failure_output="AssertionError")

    with pytest.raises(BudgetExceededError):
        await generate_candidate_patch(
            sample_recipe, up, model, host, estimated_cost=0.50
        )


@pytest.mark.asyncio
async def test_candidate_generation_clean(sample_recipe: TaskRecipe):
    host = FakeHost()
    model = FakeModelAdapter()
    up = UpgradeResult(success=True, failure_output="AssertionError")

    candidate = await generate_candidate_patch(
        sample_recipe, up, model, host, estimated_cost=0.0
    )
    assert candidate.candidate_id == "candidate_1"
    assert "src/app.py" in candidate.modified_files
    assert len(model.prompts) == 1


# --- AC-7: Unified Diff Parsing and Safety Validation ---
def test_parse_modified_files():
    diff = """--- a/src/app.py
+++ b/src/app.py
@@ -1 +1 @@
-old
+new
--- a/src/utils.py
+++ b/src/utils.py
@@ -1 +1 @@
"""
    files = parse_modified_files(diff)
    assert files == ["src/app.py", "src/utils.py"]


def test_validate_patch_allowed(sample_recipe: TaskRecipe):
    diff = """--- a/src/app.py
+++ b/src/app.py
@@ -1 +1 @@
-old
+new
"""
    res = validate_patch(diff, sample_recipe)
    assert res.valid is True


def test_validate_patch_disallowed_path(sample_recipe: TaskRecipe):
    diff = """--- a/other/module.py
+++ b/other/module.py
@@ -1 +1 @@
"""
    res = validate_patch(diff, sample_recipe)
    assert res.valid is False
    assert any("outside recipe allowed source paths" in v for v in res.violations)


def test_validate_patch_path_traversal(sample_recipe: TaskRecipe):
    res = validate_patch(UNSAFE_TRAVERSAL_PATCH, sample_recipe)
    assert res.valid is False
    assert any("traversal" in v.lower() for v in res.violations)


def test_validate_patch_test_modification(sample_recipe: TaskRecipe):
    res = validate_patch(UNSAFE_TEST_PATCH, sample_recipe)
    assert res.valid is False
    assert any("not permitted" in v.lower() for v in res.violations)


def test_validate_patch_empty_diff(sample_recipe: TaskRecipe):
    res = validate_patch("", sample_recipe)
    assert res.valid is False
    assert "empty" in res.reason.lower()


# --- AC-8 & AC-9: Candidate Verification and Artifact Persistence ---
@pytest.mark.asyncio
async def test_verify_candidate_patch_success(sample_recipe: TaskRecipe):
    host = FakeHost()
    sandbox = FakeSandboxAdapter(preset=SandboxPreset.SUCCESS)
    candidate = CandidatePatch(
        candidate_id="cand-1",
        diff_content="--- a/src/app.py\n+++ b/src/app.py\n",
        modified_files=["src/app.py"],
    )

    ver = await verify_candidate_patch(
        candidate, sample_recipe, sandbox, host, baseline_collected_count=2
    )
    assert ver.passed is True
    assert ver.collected_count == 2

    # Verify artifacts persisted
    artifact_names = [a["filename"] for a in host.artifacts]
    assert "patch.diff" in artifact_names
    assert "verify.log" in artifact_names

    # Verify events
    cand_events = [e for e in host.events if e["type"] == "candidate.completed"]
    assert len(cand_events) == 1
    assert cand_events[0]["payload"]["passed"] is True


@pytest.mark.asyncio
async def test_verify_candidate_patch_fails_tests(sample_recipe: TaskRecipe):
    host = FakeHost()
    sandbox = FakeSandboxAdapter(preset=SandboxPreset.VERIFY_TEST_FAIL)
    candidate = CandidatePatch(
        candidate_id="cand-1",
        diff_content="--- a/src/app.py\n+++ b/src/app.py\n",
        modified_files=["src/app.py"],
    )

    ver = await verify_candidate_patch(
        candidate, sample_recipe, sandbox, host, baseline_collected_count=2
    )
    assert ver.passed is False
    assert "non-zero test exit code" in ver.summary


@pytest.mark.asyncio
async def test_verify_candidate_patch_collection_mismatch(sample_recipe: TaskRecipe):
    host = FakeHost()
    sandbox = FakeSandboxAdapter(preset=SandboxPreset.VERIFY_COLLECTION_MISMATCH)
    candidate = CandidatePatch(
        candidate_id="cand-1",
        diff_content="--- a/src/app.py\n+++ b/src/app.py\n",
        modified_files=["src/app.py"],
    )

    ver = await verify_candidate_patch(
        candidate, sample_recipe, sandbox, host, baseline_collected_count=2
    )
    assert ver.passed is False
    assert "collection count mismatch" in ver.summary


@pytest.mark.asyncio
async def test_verify_candidate_patch_new_skips(sample_recipe: TaskRecipe):
    host = FakeHost()
    sandbox = FakeSandboxAdapter(preset=SandboxPreset.VERIFY_NEW_SKIPS)
    candidate = CandidatePatch(
        candidate_id="cand-1",
        diff_content="--- a/src/app.py\n+++ b/src/app.py\n",
        modified_files=["src/app.py"],
    )

    ver = await verify_candidate_patch(
        candidate, sample_recipe, sandbox, host, baseline_collected_count=2
    )
    assert ver.passed is False
    assert "newly skipped tests" in ver.summary


# --- AC-10: Cooperative Cancellation ---
@pytest.mark.asyncio
async def test_cancellation_during_sequential_repair(
    sample_request: RepairRequest, sample_recipe: TaskRecipe
):
    host = FakeHost()
    sandbox = FakeSandboxAdapter(preset=SandboxPreset.SUCCESS)

    call_idx = 0
    original_execute = sandbox.execute_command

    async def cancel_after_two(cmd, timeout_seconds=60):
        nonlocal call_idx
        call_idx += 1
        if call_idx > 2:
            host.is_cancelled = True
        return await original_execute(cmd, timeout_seconds)

    sandbox.execute_command = cancel_after_two  # type: ignore

    res = await repair(sample_request, sample_recipe, host, sandbox=sandbox)
    assert res.state == "cancelled"


# --- AC-11: Full End-to-End Offline Sequential Repair Success ---
@pytest.mark.asyncio
async def test_full_sequential_repair_pipeline_success(
    sample_request: RepairRequest, sample_recipe: TaskRecipe
):
    host = FakeHost()
    sandbox = FakeSandboxAdapter(preset=SandboxPreset.SUCCESS)
    model = FakeModelAdapter()

    result = await repair(
        sample_request, sample_recipe, host, sandbox=sandbox, model=model
    )

    assert result.state == "succeeded"
    assert "Candidate verified cleanly" in (result.reason or "")

    # Artifacts saved
    artifact_names = [a["filename"] for a in host.artifacts]
    assert "patch.diff" in artifact_names
    assert "verify.log" in artifact_names

    # Events emitted
    stage_events = [e for e in host.events if e["type"] == "stage.completed"]
    stages = [e["payload"]["stage"] for e in stage_events]
    assert "baseline" in stages
    assert "upgrade" in stages
    assert "verification" in stages

    cand_events = [e for e in host.events if e["type"] == "candidate.completed"]
    assert len(cand_events) == 1
    assert cand_events[0]["payload"]["passed"] is True

    # Reservations and settlements verified
    assert "candidate_gen_candidate_1" in host.reservations
    assert host.reservations["candidate_gen_candidate_1"] == 0.05
    assert "candidate_gen_candidate_1" in host.settlements
    assert host.settlements["candidate_gen_candidate_1"] == 0.05


@pytest.mark.asyncio
async def test_sequential_repair_cancels_before_accepting_results(
    sample_request: RepairRequest, sample_recipe: TaskRecipe
):
    host = FakeHost()
    sandbox = FakeSandboxAdapter(preset=SandboxPreset.SUCCESS)
    model = FakeModelAdapter()

    check_count = 0

    async def cancel_on_last_check():
        nonlocal check_count
        check_count += 1
        # Cancel right after verification stage (on 5th check)
        return check_count >= 5

    host.cancelled = cancel_on_last_check  # type: ignore

    res = await repair(sample_request, sample_recipe, host, sandbox=sandbox, model=model)
    assert res.state == "cancelled"
    assert "cancelled" in (res.reason or "").lower()


def test_strip_code_block_extracts_diff_from_conversational_response():
    """Offline regression for live model conversational preamble stripping."""
    from src.engine.candidate_generator import _strip_code_block

    conversational_output = (
        "We are given that the error occurs in src/backend/database.py.\n"
        "Looking at the context of the function init_db():\n\n"
        "Here is the patch:\n"
        "--- a/src/backend/database.py\n"
        "+++ b/src/backend/database.py\n"
        "@@ -5,4 +5,5 @@\n"
        "-def init_db():\n"
        "-    engine.execute(text('CREATE TABLE users'))\n"
        "+def init_db():\n"
        "+    with engine.begin() as conn:\n"
        "+        conn.execute(text('CREATE TABLE users'))\n"
        "\n"
        "Note: We must not change other files or imports.\n"
        "Hope this helps resolve the failure.\n"
    )

    clean = _strip_code_block(conversational_output)
    assert clean.startswith("--- a/src/backend/database.py")
    assert clean.endswith("\n")
    assert "We are given that" not in clean
    assert "Hope this helps" not in clean
    assert "with engine.begin() as conn:" in clean


def test_clean_patch_git_apply_trailing_newline(tmp_path):
    """Offline regression proving trailing newline prevents corrupt patch errors in git apply."""
    import subprocess
    from src.engine.candidate_generator import _strip_code_block

    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=str(repo_dir), check=True, capture_output=True)

    src_dir = repo_dir / "src" / "backend"
    src_dir.mkdir(parents=True)
    db_file = src_dir / "database.py"
    db_file.write_text("def init_db():\n    engine.execute(text('CREATE TABLE users'))\n")

    subprocess.run(["git", "add", "."], cwd=str(repo_dir), check=True, capture_output=True)
    subprocess.run(["git", "-c", "user.name=RepoMedic", "-c", "user.email=ci@repo-medic.local", "commit", "-m", "init"], cwd=str(repo_dir), check=True, capture_output=True)

    raw_diff = (
        "Here is the diff:\n"
        "--- a/src/backend/database.py\n"
        "+++ b/src/backend/database.py\n"
        "@@ -1,2 +1,3 @@\n"
        " def init_db():\n"
        "-    engine.execute(text('CREATE TABLE users'))\n"
        "+    with engine.begin() as conn:\n"
        "+        conn.execute(text('CREATE TABLE users'))"
    )

    clean_diff = _strip_code_block(raw_diff)
    assert clean_diff.endswith("\n")

    patch_file = repo_dir / "candidate.patch"
    patch_file.write_text(clean_diff)

    cmd = ["git", "apply", "--whitespace=nowarn", str(patch_file)]
    res = subprocess.run(cmd, cwd=str(repo_dir), capture_output=True, text=True)
    assert res.returncode == 0
    assert "corrupt patch" not in res.stderr
    assert "with engine.begin() as conn:" in db_file.read_text()


def test_build_repair_prompt_incorporates_source_files(sample_recipe: TaskRecipe):
    """Offline regression ensuring source files are included in prompt for line context."""
    from src.engine.candidate import UpgradeResult

    upgrade = UpgradeResult(
        success=True,
        installed_version="2.0.19",
        failure_output="AttributeError: 'Engine' object has no attribute 'execute'",
        summary="reproduced expected failure",
    )
    source_files = {
        "src/backend/database.py": "def init_db():\n    engine.execute('create table')\n"
    }

    prompt = build_repair_prompt(
        recipe=sample_recipe,
        upgrade=upgrade,
        error_block="AttributeError: 'Engine' object has no attribute 'execute'",
        error_files=["src/backend/database.py"],
        source_files=source_files,
    )

    assert "--- Current source file content ---" in prompt
    assert "File: src/backend/database.py" in prompt
    assert "def init_db():" in prompt
    assert "Do NOT output conversational explanations" in prompt
    assert "with engine.begin() as conn:" in prompt


def test_normalize_diff_context_restores_blank_line(tmp_path):
    """Offline regression testing missing blank line restoration between functions."""
    import subprocess
    from src.engine.candidate_generator import _strip_code_block

    repo_dir = tmp_path / "repo_blank"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=str(repo_dir), check=True, capture_output=True)

    src_dir = repo_dir / "src" / "backend"
    src_dir.mkdir(parents=True)
    db_file = src_dir / "database.py"
    original_code = (
        "def init_db():\n"
        "    engine.execute('create')\n"
        "\n"
        "def get_user_count():\n"
        "    return engine.execute('select')\n"
    )
    db_file.write_text(original_code)

    subprocess.run(["git", "add", "."], cwd=str(repo_dir), check=True, capture_output=True)
    subprocess.run(["git", "-c", "user.name=RepoMedic", "-c", "user.email=ci@repo-medic.local", "commit", "-m", "init"], cwd=str(repo_dir), check=True, capture_output=True)

    # Patch without blank line context between functions
    raw_diff = (
        "--- a/src/backend/database.py\n"
        "+++ b/src/backend/database.py\n"
        "@@ -1,5 +1,5 @@\n"
        " def init_db():\n"
        "-    engine.execute('create')\n"
        "+    with engine.begin() as conn:\n"
        "+        conn.execute('create')\n"
        " def get_user_count():\n"
        "-    return engine.execute('select')\n"
        "+    with engine.connect() as conn:\n"
        "+        return conn.execute('select')"
    )

    clean_diff = _strip_code_block(raw_diff, source_files={"src/backend/database.py": original_code})
    patch_file = repo_dir / "candidate.patch"
    patch_file.write_text(clean_diff)

    cmd = ["git", "apply", "--recount", "--whitespace=nowarn", str(patch_file)]
    res = subprocess.run(cmd, cwd=str(repo_dir), capture_output=True, text=True)
    assert res.returncode == 0
    assert "with engine.begin() as conn:" in db_file.read_text()
    assert "with engine.connect() as conn:" in db_file.read_text()


def test_normalize_diff_context_bare_hunk_header(tmp_path):
    """Offline regression testing bare @@ hunk header repair from model outputs."""
    import subprocess
    from src.engine.candidate_generator import _strip_code_block

    repo_dir = tmp_path / "repo_bare_hunk"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=str(repo_dir), check=True, capture_output=True)

    src_dir = repo_dir / "src" / "backend"
    src_dir.mkdir(parents=True)
    db_file = src_dir / "database.py"
    original_code = (
        "from sqlalchemy import create_engine, text\n"
        "\n"
        "engine = create_engine('sqlite:///:memory:')\n"
        "\n"
        "def init_db():\n"
        "    engine.execute(text('CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)'))\n"
        "    engine.execute(text(\"INSERT INTO users (name) VALUES ('alice')\"))\n"
        "\n"
        "def get_user_count():\n"
        "    res = engine.execute(text('SELECT count(*) FROM users'))\n"
        "    return res.scalar()\n"
    )
    db_file.write_text(original_code)

    subprocess.run(["git", "add", "."], cwd=str(repo_dir), check=True, capture_output=True)
    subprocess.run(["git", "-c", "user.name=RepoMedic", "-c", "user.email=ci@repo-medic.local", "commit", "-m", "init"], cwd=str(repo_dir), check=True, capture_output=True)

    # Patch with bare @@ header reproduced from live run
    raw_diff = (
        "--- a/src/backend/database.py\n"
        "+++ b/src/backend/database.py\n"
        "@@\n"
        " from sqlalchemy import create_engine, text\n"
        "\n"
        " engine = create_engine('sqlite:///:memory:')\n"
        "\n"
        "-def init_db():\n"
        "-    engine.execute(text('CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)'))\n"
        "-    engine.execute(text(\"INSERT INTO users (name) VALUES ('alice')\"))\n"
        "-\n"
        "-def get_user_count():\n"
        "-    res = engine.execute(text('SELECT count(*) FROM users'))\n"
        "-    return res.scalar()\n"
        "+def init_db():\n"
        "+    with engine.begin() as conn:\n"
        "+        conn.execute(text('CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)'))\n"
        "+        conn.execute(text(\"INSERT INTO users (name) VALUES ('alice')\"))\n"
        "+\n"
        "+def get_user_count():\n"
        "+    with engine.begin() as conn:\n"
        "+        res = conn.execute(text('SELECT count(*) FROM users'))\n"
        "+        return res.scalar()\n"
    )

    clean_diff = _strip_code_block(raw_diff, source_files={"src/backend/database.py": original_code})
    assert "@@ -1," in clean_diff
    patch_file = repo_dir / "candidate.patch"
    patch_file.write_text(clean_diff)

    cmd = ["git", "apply", "--recount", "--whitespace=nowarn", str(patch_file)]
    res = subprocess.run(cmd, cwd=str(repo_dir), capture_output=True, text=True)
    assert res.returncode == 0
    updated_code = db_file.read_text()
    assert "with engine.begin() as conn:" in updated_code
    assert "return res.scalar()" in updated_code


def test_normalize_diff_context_trailing_delimiter_and_unidiff_zero(tmp_path):
    """Offline regression proving trailing @@ delimiter removal and unidiff zero application."""
    import subprocess
    from src.engine.candidate_generator import _strip_code_block

    repo_dir = tmp_path / "repo_trailing_delimiter"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=str(repo_dir), check=True, capture_output=True)

    src_dir = repo_dir / "src" / "backend"
    src_dir.mkdir(parents=True)
    db_file = src_dir / "database.py"
    original_code = (
        "from sqlalchemy import create_engine, text\n"
        "\n"
        "engine = create_engine('sqlite:///:memory:')\n"
        "\n"
        "def init_db():\n"
        "    engine.execute(text('CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)'))\n"
        "    engine.execute(text(\"INSERT INTO users (name) VALUES ('alice')\"))\n"
        "\n"
        "def get_user_count():\n"
        "    res = engine.execute(text('SELECT count(*) FROM users'))\n"
        "    return res.scalar()\n"
    )
    db_file.write_text(original_code)

    subprocess.run(["git", "add", "."], cwd=str(repo_dir), check=True, capture_output=True)
    subprocess.run(["git", "-c", "user.name=RepoMedic", "-c", "user.email=ci@repo-medic.local", "commit", "-m", "init"], cwd=str(repo_dir), check=True, capture_output=True)

    # Patch with trailing @@ delimiter and zero context lines as reproduced from run 5
    raw_diff = (
        "--- a/src/backend/database.py\n"
        "+++ b/src/backend/database.py\n"
        "@@ -5,4 +5,4 @@\n"
        "-def init_db():\n"
        "-    engine.execute(text('CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)'))\n"
        "-    engine.execute(text(\"INSERT INTO users (name) VALUES ('alice')\"))\n"
        "+def init_db():\n"
        "+    with engine.begin() as conn:\n"
        "+        conn.execute(text('CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)'))\n"
        "+        conn.execute(text(\"INSERT INTO users (name) VALUES ('alice')\"))\n"
        "@@\n"
    )

    clean_diff = _strip_code_block(raw_diff, source_files={"src/backend/database.py": original_code})
    # Trailing empty @@ delimiter should be removed
    assert clean_diff.strip().endswith("conn.execute(text(\"INSERT INTO users (name) VALUES ('alice')\"))")
    patch_file = repo_dir / "candidate.patch"
    patch_file.write_text(clean_diff)

    cmd = ["git", "apply", "--recount", "--unidiff-zero", "--whitespace=nowarn", str(patch_file)]
    res = subprocess.run(cmd, cwd=str(repo_dir), capture_output=True, text=True)
    assert res.returncode == 0
    updated_code = db_file.read_text()
    assert "with engine.begin() as conn:" in updated_code
