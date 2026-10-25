import asyncio
import json
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from src.contracts import HostPorts, RepairRequest, TaskRecipe
from src.engine.adapters import CommandResult
from src.engine.contree_sandbox import ConTreeSandboxAdapter, _parse_test_summary
from src.engine.repair import repair as engine_repair
from src.storage.fake_host import FakeHost


class MockContreeImage:
    """Mock ConTree image representing remote container state."""

    def __init__(
        self,
        uuid: str = "img-uuid-001",
        tag: str = "",
        exit_code: int = 0,
        stdout: str = "",
        stderr: str = "",
    ):
        self.uuid = uuid
        self.tag = tag
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        self.run_calls: List[Dict[str, Any]] = []
        self.untagged = False

    async def run(self, **kwargs):
        self.run_calls.append(kwargs)
        cmd = kwargs.get("command", "")
        args = kwargs.get("args", [])
        full_cmd = [cmd] + list(args)

        # Simulation behaviors based on command
        if full_cmd[0] == "python3" and len(full_cmd) > 1 and "-c" in full_cmd:
            code = full_cmd[full_cmd.index("-c") + 1]
            if "hashlib" in code:
                hashes = {
                    "tests/test_mod.py": "hash_test_123",
                    "pyproject.toml": "hash_config_456",
                }
                return MockContreeImage(
                    uuid="img-uuid-hash",
                    stdout=json.dumps(hashes),
                    exit_code=0,
                )
            if "__version__" in code:
                return MockContreeImage(
                    uuid="img-uuid-ver",
                    stdout="2.0.0\n",
                    exit_code=0,
                )

        if full_cmd[0] == "git" and len(full_cmd) > 1 and full_cmd[1] == "rev-parse":
            return MockContreeImage(
                uuid="img-uuid-rev",
                stdout="abcdef1234567890\n",
                exit_code=0,
            )
        if full_cmd[0] == "git" and len(full_cmd) > 1 and full_cmd[1] == "apply":
            files = kwargs.get("files", {})
            if "/tmp/candidate.patch" in files:
                return MockContreeImage(
                    uuid="img-uuid-patch",
                    stdout="Applied patch cleanly",
                    exit_code=0,
                )
        if full_cmd[0] == "pytest" or (len(full_cmd) > 1 and full_cmd[1] == "pytest"):
            return MockContreeImage(
                uuid="img-uuid-pytest",
                stdout=(
                    "tests/test_mod.py::test_alpha\ntests/test_mod.py::test_beta\n"
                    "collected 2 items\n2 passed in 0.05s\n"
                ),
                exit_code=0,
            )

        return MockContreeImage(
            uuid="img-uuid-next",
            stdout="OK",
            exit_code=0,
        )

    async def tag_as(self, tag: str):
        self.tag = tag
        return self

    async def untag(self):
        self.untagged = True


class MockImagesManager:
    def __init__(self):
        self.used_refs = []
        self.docker_refs = []
        self.image_factory = None

    async def docker(self, ref: str):
        self.docker_refs.append(ref)
        if self.image_factory:
            return self.image_factory(ref)
        return MockContreeImage(uuid="img-base-uuid", tag=ref)

    async def use(self, ref: str):
        self.used_refs.append(ref)
        if self.image_factory:
            return self.image_factory(ref)
        return MockContreeImage(uuid=ref, tag=f"branch_{ref}")


class MockContreeClient:
    def __init__(self):
        self.images = MockImagesManager()


@pytest.fixture
def mock_recipe():
    return TaskRecipe(
        task_id="task_live_001",
        title="Live Repair Task",
        repository_url="https://github.com/example/sample-repo",
        commit_sha="abcdef1234567890",
        dependency="example-pkg",
        from_version="1.0.0",
        to_version="2.0.0",
        test_command=["pytest", "tests/"],
        allowed_source_paths=["src/"],
        expected_failure="AssertionError: regression",
        timeout_seconds=60,
        max_candidates=3,
        max_refinements=1,
    )


def test_parse_test_summary_success():
    stdout = """
    tests/test_one.py::test_alpha
    tests/test_one.py::test_beta
    collected 2 items
    2 passed in 0.04s
    """
    summary = _parse_test_summary(stdout)
    assert summary["collected_count"] == 2
    assert summary["skipped_count"] == 0
    assert summary["xfailed_count"] == 0
    assert summary["collected_node_ids"] == [
        "tests/test_one.py::test_alpha",
        "tests/test_one.py::test_beta",
    ]


def test_parse_test_summary_with_skips_and_xfails():
    stdout = """
    collected 5 items
    2 passed, 2 skipped, 1 xfailed in 0.10s
    """
    summary = _parse_test_summary(stdout)
    assert summary["collected_count"] == 5
    assert summary["skipped_count"] == 2
    assert summary["xfailed_count"] == 1


@pytest.mark.asyncio
async def test_contree_adapter_missing_credentials_fails():
    with pytest.raises(ValueError, match="NEBIUS_API_KEY and NEBIUS_PROJECT_ID"):
        ConTreeSandboxAdapter(api_key="", project_id="")


@pytest.mark.asyncio
async def test_contree_adapter_repository_preparation(mock_recipe):
    client = MockContreeClient()
    adapter = ConTreeSandboxAdapter(
        api_key="mock_key",
        project_id="mock_proj",
        client=client,
    )

    await adapter.prepare_repository(mock_recipe)

    # Check git clone, checkout, rev-parse, pip install were recorded
    cmd_heads = [cmd[0] for cmd in adapter.executed_commands]
    assert "git" in cmd_heads
    assert "pip" in cmd_heads
    assert adapter.current_image is not None


@pytest.mark.asyncio
async def test_contree_adapter_repository_preparation_commit_mismatch_fails(mock_recipe):
    client = MockContreeClient()

    # Image that returns wrong commit SHA on rev-parse
    class MismatchCommitImage(MockContreeImage):
        async def run(self, **kwargs):
            cmd = kwargs.get("command", "")
            args = kwargs.get("args", [])
            if cmd == "git" and "rev-parse" in args:
                return MismatchCommitImage(stdout="wrong_commit_sha\n", exit_code=0)
            return MismatchCommitImage(exit_code=0)

    adapter = ConTreeSandboxAdapter(
        api_key="mock_key",
        project_id="mock_proj",
        client=client,
        current_image=MismatchCommitImage(),
    )

    with pytest.raises(RuntimeError, match="commit mismatch"):
        await adapter.prepare_repository(mock_recipe)


@pytest.mark.asyncio
async def test_contree_adapter_checkpoint_and_execution_branch():
    client = MockContreeClient()
    base_img = MockContreeImage(uuid="chk_upgrade_uuid_999")
    adapter = ConTreeSandboxAdapter(
        api_key="mock_key",
        project_id="mock_proj",
        client=client,
        current_image=base_img,
    )

    # Capture checkpoint
    checkpoint_id = await adapter.capture_checkpoint(tag="chk_tag_1")
    assert checkpoint_id == "chk_upgrade_uuid_999"
    assert "chk_upgrade_uuid_999" in adapter.snapshots

    # Create ephemeral execution branch
    exec_adapter = await adapter.create_execution(checkpoint_id)
    assert exec_adapter.is_execution_handle is True
    assert exec_adapter.checkpoint_id == checkpoint_id
    assert checkpoint_id in client.images.used_refs


@pytest.mark.asyncio
async def test_contree_adapter_apply_patch():
    client = MockContreeClient()
    base_img = MockContreeImage(uuid="img_patch_base")
    adapter = ConTreeSandboxAdapter(
        api_key="mock_key",
        project_id="mock_proj",
        client=client,
        current_image=base_img,
        is_execution_handle=True,
    )

    diff = "--- a/src/app.py\n+++ b/src/app.py\n@@ -1,1 +1,1 @@\n-foo\n+bar\n"
    res = await adapter.apply_patch(diff)
    assert res.exit_code == 0
    assert "Applied patch cleanly" in res.stdout
    assert base_img.run_calls[0].get("disposable") is not True


@pytest.mark.asyncio
async def test_contree_adapter_execution_handle_retains_sequential_state():
    """covers: AC-6, AC-8 - Execution handles do not pass disposable=True, preserving sequential state."""
    client = MockContreeClient()
    base_img = MockContreeImage(uuid="img_exec_base")
    adapter = ConTreeSandboxAdapter(
        api_key="mock_key",
        project_id="mock_proj",
        client=client,
        current_image=base_img,
    )

    exec_adapter = await adapter.create_execution("chk_exec_test")
    await exec_adapter.execute_command(["echo", "step1"])
    await exec_adapter.apply_patch("diff content")

    for call in base_img.run_calls:
        assert call.get("disposable") is not True


@pytest.mark.asyncio
async def test_contree_adapter_repository_preparation_fallback_install(mock_recipe):
    """covers: AC-3 - Falls back to pip install -e . when requirements.txt fails."""
    class FallbackImage(MockContreeImage):
        async def run(self, **kwargs):
            cmd = kwargs.get("command", "")
            args = kwargs.get("args", [])
            if cmd == "git" and "rev-parse" in args:
                return FallbackImage(uuid="img_rev", stdout="abcdef1234567890\n", exit_code=0)
            if cmd == "pip" and "-r" in args:
                return FallbackImage(uuid="img_pip_err", stderr="Could not open requirements.txt", exit_code=1)
            if cmd == "pip" and "-e" in args:
                return FallbackImage(uuid="img_pip_ok", stdout="Successfully installed editable", exit_code=0)
            return FallbackImage(uuid="img_ok", exit_code=0)

    client = MockContreeClient()
    client.images.image_factory = lambda ref: FallbackImage()
    adapter = ConTreeSandboxAdapter(
        api_key="mock_key",
        project_id="mock_proj",
        client=client,
    )

    await adapter.prepare_repository(mock_recipe)
    pip_cmds = [cmd for cmd in adapter.executed_commands if cmd[0] == "pip"]
    assert len(pip_cmds) == 2
    assert "-r" in pip_cmds[0]
    assert "-e" in pip_cmds[1]


@pytest.mark.asyncio
async def test_contree_adapter_repository_preparation_task_092_setup():
    """Verify that TASK-092 installs pinned baseline, sqlite driver, and test harness on fallback."""
    class Task092Image(MockContreeImage):
        async def run(self, **kwargs):
            cmd = kwargs.get("command", "")
            args = kwargs.get("args", [])
            if cmd == "git" and "rev-parse" in args:
                return Task092Image(uuid="img_rev", stdout="6b0c767588f501d5edaabb1bdf665fcf1ded88ea\n", exit_code=0)
            if cmd == "pip" and "-r" in args:
                return Task092Image(uuid="img_pip_err", stderr="psycopg2 build error", exit_code=1)
            if cmd == "pip" and "-e" in args:
                return Task092Image(uuid="img_pip_ok", stdout="Successfully installed databases", exit_code=0)
            return Task092Image(uuid="img_ok", exit_code=0)

    client = MockContreeClient()
    client.images.image_factory = lambda ref: Task092Image()
    adapter = ConTreeSandboxAdapter(
        api_key="mock_key",
        project_id="mock_proj",
        client=client,
    )

    task_092_recipe = TaskRecipe(
        task_id="TASK-092",
        title="sqlalchemy v1.4.42 to v2.0.19 in encode/databases external project",
        repository_url="https://github.com/encode/databases.git",
        commit_sha="6b0c767588f501d5edaabb1bdf665fcf1ded88ea",
        dependency="sqlalchemy",
        from_version="1.4.42",
        to_version="2.0.19",
        test_command=["env", "TEST_DATABASE_URLS=sqlite:///testsuite", "pytest", "tests/test_databases.py"],
        allowed_source_paths=["databases/core.py", "databases/backends/sqlite.py"],
        expected_failure="AttributeError: type object 'Row' has no attribute '_default_key_style'",
        timeout_seconds=600,
        max_candidates=3,
        max_refinements=1,
    )

    await adapter.prepare_repository(task_092_recipe)
    pip_cmds = [cmd for cmd in adapter.executed_commands if cmd[0] == "pip"]
    assert len(pip_cmds) == 3
    assert "-r" in pip_cmds[0]
    assert "-e" in pip_cmds[1]
    assert "sqlalchemy==1.4.42" in pip_cmds[2]
    assert "aiosqlite" in pip_cmds[2]
    assert "pytest" in pip_cmds[2]


@pytest.mark.asyncio
async def test_contree_adapter_hash_files():
    client = MockContreeClient()
    base_img = MockContreeImage(uuid="img_hash_base")
    adapter = ConTreeSandboxAdapter(
        api_key="mock_key",
        project_id="mock_proj",
        client=client,
        current_image=base_img,
    )

    hashes = await adapter.hash_files()
    assert "tests/test_mod.py" in hashes
    assert hashes["tests/test_mod.py"] == "hash_test_123"


@pytest.mark.asyncio
async def test_contree_adapter_cleanup():
    client = MockContreeClient()
    base_img = MockContreeImage(uuid="img_cleanup_base")
    adapter = ConTreeSandboxAdapter(
        api_key="mock_key",
        project_id="mock_proj",
        client=client,
        current_image=base_img,
    )

    exec_adapter = await adapter.create_execution("chk_123")
    await adapter.cleanup()

    assert adapter.cleaned_up is True
    assert exec_adapter.cleaned_up is True
    assert base_img.untagged is True


@pytest.mark.asyncio
async def test_repair_live_mode_missing_credentials_fails(mock_recipe):
    request = RepairRequest(
        run_id="run_live_test_01",
        task_id=mock_recipe.task_id,
        mode="live",
        search_mode="sequential",
        max_run_usd=2.0,
    )
    host = FakeHost()

    with patch("src.engine.repair.settings") as mock_settings:
        mock_settings.token_factory_api_key = ""
        mock_settings.nebius_api_key = ""
        mock_settings.nebius_project_id = ""

        result = await engine_repair(request, mock_recipe, host)
        assert result.state == "failed"
        assert "missing required credentials" in result.reason


@pytest.mark.asyncio
async def test_repair_live_mode_budget_enforcement(mock_recipe):
    request = RepairRequest(
        run_id="run_live_test_budget",
        task_id=mock_recipe.task_id,
        mode="live",
        search_mode="sequential",
        max_run_usd=2.0,
    )
    client = MockContreeClient()
    adapter = ConTreeSandboxAdapter(
        api_key="key",
        project_id="proj",
        client=client,
        current_image=MockContreeImage(),
    )

    # FakeHost with a tiny budget ceiling that rejects reservations
    class BudgetDeniedHost(FakeHost):
        async def reserve(self, operation_id: str, estimated_usd: float) -> bool:
            return False

    host = BudgetDeniedHost()
    result = await engine_repair(request, mock_recipe, host, sandbox=adapter)
    assert result.state == "failed"
    assert "Budget reservation" in result.reason


@pytest.mark.asyncio
async def test_repair_live_mode_responsive_cancellation(mock_recipe):
    request = RepairRequest(
        run_id="run_live_test_cancel",
        task_id=mock_recipe.task_id,
        mode="live",
        search_mode="sequential",
        max_run_usd=2.0,
    )
    client = MockContreeClient()
    adapter = ConTreeSandboxAdapter(
        api_key="key",
        project_id="proj",
        client=client,
        current_image=MockContreeImage(),
    )

    class CancelledHost(FakeHost):
        def __init__(self):
            super().__init__()
            self._cancel_count = 0

        async def cancelled(self) -> bool:
            self._cancel_count += 1
            # Return True on cancellation check after baseline stage
            return self._cancel_count >= 4

    host = CancelledHost()
    result = await engine_repair(request, mock_recipe, host, sandbox=adapter)
    assert result.state == "cancelled"


@pytest.mark.asyncio
async def test_repair_live_mode_clean_sequential_success(mock_recipe):
    request = RepairRequest(
        run_id="run_live_test_success",
        task_id=mock_recipe.task_id,
        mode="live",
        search_mode="sequential",
        max_run_usd=2.0,
    )

    class SequentialMockImage(MockContreeImage):
        def __init__(self, upgrade_installed=False, patch_applied=False):
            super().__init__()
            self.upgrade_installed = upgrade_installed
            self.patch_applied = patch_applied

        async def run(self, **kwargs):
            cmd = kwargs.get("command", "")
            args = kwargs.get("args", [])

            # Rev-parse for repo prep
            if cmd == "git" and "rev-parse" in args:
                img = SequentialMockImage(self.upgrade_installed, self.patch_applied)
                img.stdout = "abcdef1234567890\n"
                return img

            # pip install
            if cmd == "pip":
                is_up = self.upgrade_installed or any("==" in str(a) for a in args)
                img = SequentialMockImage(upgrade_installed=is_up, patch_applied=self.patch_applied)
                img.stdout = "Successfully installed"
                return img

            # Hash script
            if cmd == "python3" and len(args) > 1 and "-c" in args:
                code = args[args.index("-c") + 1]
                if "hashlib" in code:
                    hashes = {
                        "tests/test_app.py": "hash_app_01",
                        "pyproject.toml": "hash_toml_01",
                    }
                    img = SequentialMockImage(self.upgrade_installed, self.patch_applied)
                    img.stdout = json.dumps(hashes)
                    return img
                if "__version__" in code:
                    img = SequentialMockImage(self.upgrade_installed, self.patch_applied)
                    img.stdout = "2.0.0\n"
                    return img

            # Git apply patch
            if cmd == "git" and "apply" in args:
                img = SequentialMockImage(upgrade_installed=self.upgrade_installed, patch_applied=True)
                img.stdout = "Applied patch cleanly"
                return img

            # Pytest execution
            if cmd == "pytest":
                img = SequentialMockImage(self.upgrade_installed, self.patch_applied)
                if self.upgrade_installed and not self.patch_applied:
                    # Post-upgrade failure reproduction
                    img.stdout = "collected 2 items\n"
                    img.stderr = "AssertionError: regression\n"
                    img.exit_code = 1
                else:
                    # Baseline or post-patch verification
                    img.stdout = "tests/test_app.py::test_one\n2 passed in 0.05s\n"
                    img.exit_code = 0
                return img

            return SequentialMockImage(self.upgrade_installed, self.patch_applied)

    client = MockContreeClient()
    client.images.image_factory = lambda ref: SequentialMockImage(upgrade_installed=True)
    adapter = ConTreeSandboxAdapter(
        api_key="key",
        project_id="proj",
        client=client,
        current_image=SequentialMockImage(),
    )

    class MockModelAdapter:
        async def complete(self, prompt: str, max_tokens: int = 2048) -> str:
            return (
                "```diff\n"
                "--- a/src/app.py\n"
                "+++ b/src/app.py\n"
                "@@ -1,1 +1,1 @@\n"
                "-old()\n"
                "+new()\n"
                "```"
            )

    host = FakeHost()
    result = await engine_repair(
        request=request,
        recipe=mock_recipe,
        host=host,
        sandbox=adapter,
        model=MockModelAdapter(),
    )
    assert result.state == "succeeded"
    assert "Candidate verified cleanly" in result.reason
    assert "sandbox:setup" in host.settlements
    assert host.settlements["sandbox:setup"] == 0.20
    assert "candidate_gen_candidate_1" in host.settlements
    assert host.settlements["candidate_gen_candidate_1"] == 0.05
    assert "sandbox:verify:candidate_1" in host.settlements
    assert host.settlements["sandbox:verify:candidate_1"] == 0.10


@pytest.mark.asyncio
async def test_worker_live_mode_missing_credentials_fails_without_fake_fallback(mock_recipe):
    from src.storage.db_client import RepoMedicDB
    from src.storage.repository import D1StorageRepository
    from src.worker import QueueWorker
    from tests.test_storage import create_sqlite_d1_transport

    transport = create_sqlite_d1_transport(expected_token="test-bridge-token")
    mock_db = RepoMedicDB(
        base_url="http://test-bridge",
        api_key="test-bridge-token",
        transport=transport,
    )
    repo = D1StorageRepository(mock_db)
    repo.upsert_task({
        "task_id": mock_recipe.task_id,
        "title": mock_recipe.title,
        "repository_url": mock_recipe.repository_url,
        "commit_sha": mock_recipe.commit_sha,
        "dependency": mock_recipe.dependency,
        "from_version": mock_recipe.from_version,
        "to_version": mock_recipe.to_version,
    })
    run = repo.create_run(
        run_id="run_live_worker_test_01",
        task_id=mock_recipe.task_id,
        mode="live",
        search_mode="sequential",
    )

    from src.config import settings
    with patch.object(settings, "token_factory_api_key", ""), \
         patch.object(settings, "nebius_api_key", ""), \
         patch.object(settings, "nebius_project_id", ""):

        worker = QueueWorker(repo=repo)
        processed = await worker.process_one()
        assert processed is True

        updated_run = repo.get_run(run.run_id)
        assert updated_run.state == "failed"
        assert "missing required credentials" in (updated_run.reason or "")
