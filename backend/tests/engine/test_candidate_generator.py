"""Unit tests for engine candidate generator functions."""

import pytest

from src.contracts import TaskRecipe
from src.engine.candidate import UpgradeResult
from src.engine.candidate_generator import (
    _strip_code_block,
    build_repair_prompt,
    generate_candidate_patch,
    normalize_diff_context,
)
from src.engine.fake_model import FakeModelAdapter
from src.storage.fake_host import FakeHost


@pytest.fixture
def sample_recipe() -> TaskRecipe:
    return TaskRecipe(
        task_id="TASK-TEST-001",
        title="Sample Test Migration",
        repository_url="https://github.com/example/repo.git",
        commit_sha="abcdef1234567890",
        dependency="sqlalchemy",
        from_version="1.4.48",
        to_version="2.0.19",
        test_command=["pytest", "tests/"],
        allowed_source_paths=["src/app.py"],
        expected_failure="AttributeError: 'Engine' object has no attribute 'execute'",
        timeout_seconds=300,
        max_candidates=3,
        max_refinements=1,
    )


def test_build_repair_prompt_includes_source_files(sample_recipe):
    """Verify build_repair_prompt formats allowed paths and embedded source files."""
    upgrade = UpgradeResult(
        success=False,
        failure_output="AttributeError: 'Engine' object has no attribute 'execute'",
    )
    sources = {"src/app.py": "import sqlalchemy\ndef run():\n    pass\n"}
    prompt = build_repair_prompt(
        recipe=sample_recipe,
        upgrade=upgrade,
        error_block="AttributeError: execute missing",
        error_files=["src/app.py"],
        source_files=sources,
    )

    assert "src/app.py" in prompt
    assert "import sqlalchemy" in prompt
    assert "Allowed source paths: src/app.py" in prompt
    assert "SQLAlchemy 2.0 upgrades" in prompt


def test_strip_code_block_cleans_fenced_markdown_and_commentary():
    """Verify markdown fences and trailing text are stripped from model output."""
    raw = (
        "Here is the patch you requested:\n"
        "```diff\n"
        "--- a/src/app.py\n"
        "+++ b/src/app.py\n"
        "@@ -1,3 +1,3 @@\n"
        " context line\n"
        "-engine.execute('SELECT 1')\n"
        "+with engine.begin() as conn: conn.execute('SELECT 1')\n"
        " trailing context\n"
        "```\n"
        "Let me know if you need more changes."
    )
    cleaned = _strip_code_block(raw)
    assert cleaned.startswith("--- a/src/app.py\n")
    assert "with engine.begin()" in cleaned
    assert "Let me know if you need more changes" not in cleaned


def test_normalize_diff_context_repairs_bare_hunk_headers():
    """Verify bare hunk headers without counts are repaired."""
    raw_diff = (
        "--- a/src/app.py\n"
        "+++ b/src/app.py\n"
        "@@\n"
        " context line\n"
        "-old\n"
        "+new\n"
    )
    normalized = normalize_diff_context(raw_diff)
    assert "@@ -1,2 +1,2 @@" in normalized


@pytest.mark.asyncio
async def test_generate_candidate_patch_emits_usage_updated(sample_recipe):
    """Verify candidate patch generation settles budget and emits usage.updated event."""
    upgrade = UpgradeResult(
        success=False,
        failure_output="AttributeError: 'Engine' object has no attribute 'execute'",
    )
    host = FakeHost()
    canned_diff = (
        "--- a/src/app.py\n"
        "+++ b/src/app.py\n"
        "@@ -1,2 +1,2 @@\n"
        "-old\n"
        "+new\n"
    )
    model = FakeModelAdapter(canned_responses=[canned_diff])

    patch = await generate_candidate_patch(
        recipe=sample_recipe,
        upgrade=upgrade,
        model=model,
        host=host,
        candidate_id="candidate_1",
        estimated_cost=0.05,
    )

    assert patch.candidate_id == "candidate_1"
    assert "--- a/src/app.py" in patch.diff_content
    assert host.settlements.get("candidate_gen_candidate_1") == 0.05

    usage_events = [e for e in host.events if e["type"] == "usage.updated"]
    assert len(usage_events) == 1
    assert usage_events[0]["payload"]["model_calls"] == 1
    assert usage_events[0]["payload"]["estimated_usd"] == 0.05


def test_build_repair_prompt_sqlalchemy_2_rules(sample_recipe):
    """Verify prompt guides SQLAlchemy 2.0 Row signature changes without hardcoded functions."""
    upgrade = UpgradeResult(
        success=False,
        failure_output="AttributeError: type object 'Row' has no attribute '_default_key_style'",
    )
    prompt = build_repair_prompt(
        recipe=sample_recipe,
        upgrade=upgrade,
        error_block="Row has no attribute '_default_key_style'",
        error_files=["databases/backends/sqlite.py"],
    )
    assert "_default_key_style" in prompt
    assert "init_db" not in prompt


def test_strip_code_block_computes_diff_from_python_code_block():
    """Verify that when model outputs an updated python code block, unified diff is computed against source_files."""
    orig = "def foo():\n    return 1\n"
    updated_code = "```python\ndef foo():\n    return 2\n```"
    diff = _strip_code_block(updated_code, source_files={"src/foo.py": orig})
    assert "--- a/src/foo.py" in diff
    assert "+++ b/src/foo.py" in diff
    assert "+    return 2" in diff
    assert "-    return 1" in diff


def test_candidate_generator_preamble_without_diff_header_rejection():
    """Verify conversational text exceeding tokens or omitting diff headers is rejected safely."""
    from src.engine.patch_validator import parse_modified_files, validate_patch

    conversational_preamble = (
        "Based on my analysis of the error in databases/backends/sqlite.py, "
        "the issue is that Row no longer accepts _default_key_style in SQLAlchemy 2.0. "
        "You should remove _default_key_style from the Row instantiation call."
    )
    cleaned = _strip_code_block(conversational_preamble)
    modified = parse_modified_files(cleaned)
    assert modified == []

    dummy_recipe = TaskRecipe(
        task_id="TASK-DUMMY",
        title="Dummy",
        repository_url="https://github.com/example/repo",
        commit_sha="123456",
        dependency="pkg",
        from_version="1.0",
        to_version="2.0",
        test_command=["pytest"],
        allowed_source_paths=["src/"],
        expected_failure="Error",
        timeout_seconds=60,
        max_candidates=3,
        max_refinements=1,
    )
    res = validate_patch(cleaned, dummy_recipe)
    assert res.valid is False
    assert res.reason == "No modified file targets found in patch header"


@pytest.mark.asyncio
async def test_repair_filters_source_files_to_failing_error_files():
    """Verify repair only loads source files matching detected error files to prevent token bloat."""
    from src.contracts import RepairRequest
    from src.engine.adapters import CommandResult
    from src.engine.fake_sandbox import FakeSandboxAdapter
    from src.engine.repair import repair

    recipe = TaskRecipe(
        task_id="TASK-FILTER-01",
        title="Filter Test",
        repository_url="https://github.com/example/repo",
        commit_sha="123456",
        dependency="sqlalchemy",
        from_version="1.4.42",
        to_version="2.0.19",
        test_command=["pytest", "tests/"],
        allowed_source_paths=["databases/core.py", "databases/backends/sqlite.py"],
        expected_failure="Row has no attribute '_default_key_style'",
        timeout_seconds=60,
        max_candidates=3,
        max_refinements=1,
    )

    cat_calls = []

    class FilteringSandbox(FakeSandboxAdapter):
        async def execute_command(self, command, timeout_seconds=60):
            if command[0] == "cat":
                cat_calls.append(command[1])
                return CommandResult(exit_code=0, stdout="content of " + command[1])
            return await super().execute_command(command, timeout_seconds)

    class CapturingModel(FakeModelAdapter):
        def __init__(self):
            canned = (
                "--- a/databases/backends/sqlite.py\n"
                "+++ b/databases/backends/sqlite.py\n"
                "@@ -1,1 +1,1 @@\n"
                "-old\n"
                "+new\n"
            )
            super().__init__(canned_response=canned)
            self.last_prompt = ""

        async def complete(self, prompt: str, max_tokens: int = 2048) -> str:
            self.last_prompt = prompt
            return self.canned_response

    failure_tb = (
        'Traceback (most recent call last):\n'
        '  File "databases/backends/sqlite.py", line 106, in fetch_all\n'
        'AttributeError: Row has no attribute \'_default_key_style\''
    )
    sandbox = FilteringSandbox(reproduced_failure_stderr=failure_tb)
    model = CapturingModel()
    host = FakeHost()
    request = RepairRequest(
        run_id="run_filter_test",
        task_id="TASK-FILTER-01",
        mode="offline",
        search_mode="sequential",
        max_run_usd=2.0,
    )

    await repair(request, recipe, host, sandbox=sandbox, model=model)

    # databases/core.py was not in failure output, so only failing file sqlite.py was read
    assert "databases/backends/sqlite.py" in cat_calls
    assert "databases/core.py" not in cat_calls
    assert "File: databases/backends/sqlite.py" in model.last_prompt
    assert "File: databases/core.py" not in model.last_prompt
