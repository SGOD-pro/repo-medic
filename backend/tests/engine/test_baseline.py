import pytest
from src.contracts import EventEnvelope, RepairRequest, TaskRecipe
from src.engine.adapters import CommandResult, SandboxPreset
from src.engine.baseline import run_baseline_stage
from src.engine.fake_model import FakeModelAdapter
from src.engine.fake_sandbox import FakeSandboxAdapter
from src.engine.repair import repair
from src.engine.validation import RecipeValidationError, validate_recipe
from src.storage.fake_host import FakeHost


@pytest.fixture
def valid_recipe() -> TaskRecipe:
    return TaskRecipe(
        task_id="test-task-1",
        title="Test Upgrade Task",
        repository_url="https://github.com/example/repo",
        commit_sha="1234567890abcdef",
        dependency="pytest-mock",
        from_version="3.10.0",
        to_version="3.11.1",
        test_command=["pytest", "tests/"],
        allowed_source_paths=["src/"],
        expected_failure="AssertionError",
        timeout_seconds=60,
        max_candidates=1,
        max_refinements=0,
    )


@pytest.fixture
def valid_request() -> RepairRequest:
    return RepairRequest(
        run_id="run-001",
        task_id="test-task-1",
        mode="offline",
        search_mode="sequential",
        max_run_usd=1.0,
    )


# --- AC-1 & AC-2: Recipe Validation Tests ---


def test_recipe_validation_success(valid_recipe):
    # covers: AC-1
    # Valid recipe should not raise any validation error
    validate_recipe(valid_recipe)


def test_recipe_validation_empty_task_id(valid_recipe):
    # covers: AC-1
    recipe = valid_recipe.model_copy(update={"task_id": "  "})
    with pytest.raises(RecipeValidationError, match="task_id must be a non-empty string"):
        validate_recipe(recipe)


def test_recipe_validation_empty_repository_url(valid_recipe):
    # covers: AC-1
    recipe = valid_recipe.model_copy(update={"repository_url": ""})
    with pytest.raises(RecipeValidationError, match="repository_url must be a non-empty string"):
        validate_recipe(recipe)


def test_recipe_validation_empty_commit_sha(valid_recipe):
    # covers: AC-1
    recipe = valid_recipe.model_copy(update={"commit_sha": ""})
    with pytest.raises(RecipeValidationError, match="commit_sha must be a non-empty string"):
        validate_recipe(recipe)


def test_recipe_validation_empty_expected_failure(valid_recipe):
    # covers: AC-1
    recipe = valid_recipe.model_copy(update={"expected_failure": ""})
    with pytest.raises(RecipeValidationError, match="expected_failure must be a non-empty string"):
        validate_recipe(recipe)


def test_recipe_validation_empty_test_command(valid_recipe):
    # covers: AC-1
    recipe = valid_recipe.model_copy(update={"test_command": []})
    with pytest.raises(RecipeValidationError, match="test_command must not be empty"):
        validate_recipe(recipe)


def test_recipe_validation_whitespace_test_command(valid_recipe):
    # covers: AC-1
    recipe = valid_recipe.model_copy(update={"test_command": ["   "]})
    with pytest.raises(RecipeValidationError, match="test_command must contain non-empty"):
        validate_recipe(recipe)


def test_recipe_validation_non_positive_timeout(valid_recipe):
    # covers: AC-1
    recipe = valid_recipe.model_copy(update={"timeout_seconds": 0})
    with pytest.raises(RecipeValidationError, match="timeout_seconds must be positive"):
        validate_recipe(recipe)


def test_recipe_validation_empty_allowed_source_paths(valid_recipe):
    # covers: AC-1
    recipe = valid_recipe.model_copy(update={"allowed_source_paths": []})
    with pytest.raises(RecipeValidationError, match="allowed_source_paths must not be empty"):
        validate_recipe(recipe)


def test_recipe_validation_whitespace_allowed_source_path(valid_recipe):
    # covers: AC-1
    recipe = valid_recipe.model_copy(update={"allowed_source_paths": ["   "]})
    with pytest.raises(RecipeValidationError, match="allowed_source_paths contains an empty path"):
        validate_recipe(recipe)


def test_recipe_validation_absolute_source_path(valid_recipe):
    # covers: AC-1
    recipe = valid_recipe.model_copy(update={"allowed_source_paths": ["/etc/passwd"]})
    with pytest.raises(RecipeValidationError, match="must be relative, got absolute path"):
        validate_recipe(recipe)


def test_recipe_validation_parent_traversal_source_path(valid_recipe):
    # covers: AC-1
    recipe = valid_recipe.model_copy(update={"allowed_source_paths": ["src/../../outside"]})
    with pytest.raises(RecipeValidationError, match="cannot traverse parent directories"):
        validate_recipe(recipe)


def test_recipe_validation_backslash_traversal_source_path(valid_recipe):
    # covers: AC-1
    recipe = valid_recipe.model_copy(update={"allowed_source_paths": ["src\\..\\outside"]})
    with pytest.raises(RecipeValidationError, match="cannot traverse parent directories"):
        validate_recipe(recipe)


@pytest.mark.asyncio
async def test_repair_fails_immediately_on_invalid_recipe(valid_request, valid_recipe):
    # covers: AC-2
    # invalid recipe returns failed RepairResult immediately without emitting events
    invalid_recipe = valid_recipe.model_copy(update={"timeout_seconds": -5})
    host = FakeHost()

    result = await repair(valid_request, invalid_recipe, host)

    assert result.state == "failed"
    assert "Recipe validation failed" in (result.reason or "")
    # Must NOT emit stage.completed or any other event
    assert len(host.events) == 0


# --- AC-3 & AC-4: Fake Adapters Tests ---


@pytest.mark.asyncio
async def test_fake_sandbox_presets():
    # covers: AC-3
    # Configurable presets
    sandbox_success = FakeSandboxAdapter(SandboxPreset.SUCCESS)
    res = await sandbox_success.execute_command(["pytest"])
    assert res.exit_code == 0
    assert res.collected_count == 2
    assert sandbox_success.call_count == 1
    assert sandbox_success.executed_commands == [["pytest"]]

    # FIRST_FAIL
    sandbox_ff = FakeSandboxAdapter(SandboxPreset.FIRST_FAIL)
    res1 = await sandbox_ff.execute_command(["pytest"])
    assert res1.exit_code == 1
    assert "AssertionError" in res1.stderr

    # SECOND_FAIL
    sandbox_sf = FakeSandboxAdapter(SandboxPreset.SECOND_FAIL)
    res_sf1 = await sandbox_sf.execute_command(["pytest"])
    assert res_sf1.exit_code == 0
    res_sf2 = await sandbox_sf.execute_command(["pytest"])
    assert res_sf2.exit_code == 1

    # UNSTABLE_COLLECTION
    sandbox_uc = FakeSandboxAdapter(SandboxPreset.UNSTABLE_COLLECTION)
    res_uc1 = await sandbox_uc.execute_command(["pytest"])
    res_uc2 = await sandbox_uc.execute_command(["pytest"])
    assert res_uc1.collected_count != res_uc2.collected_count

    # TIMEOUT
    sandbox_to = FakeSandboxAdapter(SandboxPreset.TIMEOUT)
    with pytest.raises(TimeoutError):
        await sandbox_to.execute_command(["pytest"])


@pytest.mark.asyncio
async def test_fake_model_adapter():
    # covers: AC-4
    # Model adapter protocol completion
    model = FakeModelAdapter(canned_response="diff --git a/src b/src")
    completion = await model.complete("Generate fix", max_tokens=100)
    assert completion == "diff --git a/src b/src"
    assert model.call_count == 1
    assert model.prompts == ["Generate fix"]


# --- AC-5, AC-8, AC-10: Baseline Happy Path & Invariants ---


@pytest.mark.asyncio
async def test_baseline_success(valid_request, valid_recipe):
    # covers: AC-5, AC-8, AC-10
    # Two clean passes with stable collection emit stage.completed passed=True
    host = FakeHost()
    sandbox = FakeSandboxAdapter(SandboxPreset.SUCCESS)

    outcome = await run_baseline_stage(valid_recipe, sandbox, host)

    assert outcome.passed is True
    assert sandbox.call_count == 2
    assert sandbox.executed_commands == [valid_recipe.test_command, valid_recipe.test_command]

    # AC-10: zero budget reservations in offline fake mode
    assert len(host.reservations) == 0

    # Invariants: Exactly one stage.completed event, passed=True, never run.finished
    assert len(host.events) == 1
    event = host.events[0]
    assert event["type"] == "stage.completed"
    assert event["payload"]["stage"] == "baseline"
    assert event["payload"]["passed"] is True
    assert "twice with stable collection" in event["payload"]["summary"]

    # Validate event envelope compatibility
    env = EventEnvelope(
        run_id=valid_request.run_id,
        seq=1,
        ts="2026-10-10T00:00:00Z",
        type=event["type"],
        payload=event["payload"],
    )
    assert env.type == "stage.completed"


# --- AC-6: First Check Failure & Execution Errors ---


@pytest.mark.asyncio
async def test_baseline_first_check_failure(valid_request, valid_recipe):
    # covers: AC-6
    # First baseline execution failure emits passed=False and fails repair
    host = FakeHost()
    sandbox = FakeSandboxAdapter(SandboxPreset.FIRST_FAIL)

    result = await repair(valid_request, valid_recipe, host, sandbox=sandbox)

    assert result.state == "failed"
    assert "Baseline check 1 failed" in (result.reason or "")
    # Should stop after check 1, not running check 2
    assert sandbox.call_count == 1

    assert len(host.events) == 1
    event = host.events[0]
    assert event["type"] == "stage.completed"
    assert event["payload"]["stage"] == "baseline"
    assert event["payload"]["passed"] is False
    assert "Baseline check 1 failed" in event["payload"]["summary"]


@pytest.mark.asyncio
async def test_baseline_first_check_execution_exception(valid_request, valid_recipe):
    # covers: AC-6
    # Unexpected exception in first check emits passed=False
    class CrashingSandbox(FakeSandboxAdapter):
        async def execute_command(self, command, timeout_seconds=60):
            raise RuntimeError("Unexpected container crash")

    host = FakeHost()
    sandbox = CrashingSandbox()
    result = await repair(valid_request, valid_recipe, host, sandbox=sandbox)

    assert result.state == "failed"
    assert "Unexpected container crash" in (result.reason or "")
    assert len(host.events) == 1
    assert host.events[0]["payload"]["passed"] is False


# --- AC-7: Second Check Failure & Unstable Collection ---


@pytest.mark.asyncio
async def test_baseline_second_check_failure_instability(valid_request, valid_recipe):
    # covers: AC-7
    # Second check failure reports instability
    host = FakeHost()
    sandbox = FakeSandboxAdapter(SandboxPreset.SECOND_FAIL)

    result = await repair(valid_request, valid_recipe, host, sandbox=sandbox)

    assert result.state == "failed"
    assert "instability" in (result.reason or "")
    assert sandbox.call_count == 2

    assert len(host.events) == 1
    event = host.events[0]
    assert event["payload"]["stage"] == "baseline"
    assert event["payload"]["passed"] is False
    assert "instability" in event["payload"]["summary"]


@pytest.mark.asyncio
async def test_baseline_second_check_stdout_fallback(valid_request, valid_recipe):
    # covers: AC-7
    # Nonzero exit code on check 2 with empty stderr falls back to stdout
    class StdoutOnlySandbox(FakeSandboxAdapter):
        async def execute_command(self, command, timeout_seconds=60):
            self.call_count += 1
            if self.call_count == 1:
                return CommandResult(exit_code=0, stdout="clean", stderr="", collected_count=2)
            return CommandResult(exit_code=2, stdout="Check 2 stdout failure", stderr="", collected_count=2)

    host = FakeHost()
    sandbox = StdoutOnlySandbox()
    result = await repair(valid_request, valid_recipe, host, sandbox=sandbox)

    assert result.state == "failed"
    assert "Check 2 stdout failure" in (result.reason or "")
    assert host.events[0]["payload"]["passed"] is False


@pytest.mark.asyncio
async def test_baseline_second_check_execution_exception(valid_request, valid_recipe):
    # covers: AC-7
    # Unexpected exception in second check emits passed=False
    class CrashingSecondSandbox(FakeSandboxAdapter):
        async def execute_command(self, command, timeout_seconds=60):
            self.call_count += 1
            if self.call_count == 1:
                return CommandResult(exit_code=0, stdout="pass", stderr="", collected_count=2)
            raise RuntimeError("Check 2 crash")

    host = FakeHost()
    sandbox = CrashingSecondSandbox()
    result = await repair(valid_request, valid_recipe, host, sandbox=sandbox)

    assert result.state == "failed"
    assert "Check 2 crash" in (result.reason or "")
    assert host.events[0]["payload"]["passed"] is False


@pytest.mark.asyncio
async def test_baseline_unstable_collection_failure(valid_request, valid_recipe):
    # covers: AC-7
    # Differing test counts report collection instability
    host = FakeHost()
    sandbox = FakeSandboxAdapter(SandboxPreset.UNSTABLE_COLLECTION)

    result = await repair(valid_request, valid_recipe, host, sandbox=sandbox)

    assert result.state == "failed"
    assert "test collection unstable" in (result.reason or "")
    assert sandbox.call_count == 2

    assert len(host.events) == 1
    event = host.events[0]
    assert event["payload"]["stage"] == "baseline"
    assert event["payload"]["passed"] is False
    assert "unstable" in event["payload"]["summary"]


@pytest.mark.asyncio
async def test_baseline_timeout_failure(valid_request, valid_recipe):
    # covers: AC-6
    # Timeout in baseline execution reports timeout error
    host = FakeHost()
    sandbox = FakeSandboxAdapter(SandboxPreset.TIMEOUT)

    result = await repair(valid_request, valid_recipe, host, sandbox=sandbox)

    assert result.state == "failed"
    assert "timed out" in (result.reason or "")

    assert len(host.events) == 1
    event = host.events[0]
    assert event["payload"]["stage"] == "baseline"
    assert event["payload"]["passed"] is False
    assert "timed out" in event["payload"]["summary"]


# --- AC-9: Cancellation Behavior ---


@pytest.mark.asyncio
async def test_cancellation_before_execution(valid_request, valid_recipe):
    # covers: AC-9
    host = FakeHost()
    host.is_cancelled = True
    sandbox = FakeSandboxAdapter()

    result = await repair(valid_request, valid_recipe, host, sandbox=sandbox)

    assert result.state == "cancelled"
    assert sandbox.call_count == 0
    assert len(host.events) == 0


@pytest.mark.asyncio
async def test_cancellation_between_checks(valid_request, valid_recipe):
    # covers: AC-9
    # Custom host that cancels after the first check executes
    class DynamicCancellingHost(FakeHost):
        def __init__(self):
            super().__init__()
            self._checks_seen = 0

    host = DynamicCancellingHost()

    class InterceptingSandbox(FakeSandboxAdapter):
        async def execute_command(self, command, timeout_seconds=60):
            res = await super().execute_command(command, timeout_seconds)
            # Trigger cancellation after check 1 finishes
            host.is_cancelled = True
            return res

    sandbox = InterceptingSandbox(SandboxPreset.SUCCESS)
    result = await repair(valid_request, valid_recipe, host, sandbox=sandbox)

    assert result.state == "cancelled"
    assert sandbox.call_count == 1
    assert "cancelled between baseline checks" in (result.reason or "")
    # Should not emit stage.completed
    assert len(host.events) == 0


@pytest.mark.asyncio
async def test_cancellation_after_second_check(valid_request, valid_recipe):
    # covers: AC-9
    # Cancellation triggered after check 2 finishes before declaring success
    host = FakeHost()

    class InterceptingCheck2Sandbox(FakeSandboxAdapter):
        async def execute_command(self, command, timeout_seconds=60):
            res = await super().execute_command(command, timeout_seconds)
            if self.call_count == 2:
                host.is_cancelled = True
            return res

    sandbox = InterceptingCheck2Sandbox(SandboxPreset.SUCCESS)
    result = await repair(valid_request, valid_recipe, host, sandbox=sandbox)

    assert result.state == "cancelled"
    assert sandbox.call_count == 2
    assert "cancelled after baseline checks" in (result.reason or "")
    assert len(host.events) == 0
