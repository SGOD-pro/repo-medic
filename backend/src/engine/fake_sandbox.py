from typing import Dict, List, Optional
from src.engine.adapters import CommandResult, SandboxAdapter, SandboxPreset


class FakeSandboxAdapter(SandboxAdapter):
    """
    In-memory deterministic sandbox adapter for engine testing.
    Supports configurable simulation presets across baseline, upgrade, and verification stages.
    """

    DEFAULT_TEST_HASHES = {
        "tests/test_app.py": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "tests/conftest.py": "ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb",
        "pyproject.toml": "3e23e8160039594a33894f6564e1b1348bbd7a0088d42c4acb73eeaed59c009d",
    }
    DEFAULT_NODE_IDS = ["tests/test_app.py::test_one", "tests/test_app.py::test_two"]

    def __init__(
        self,
        preset: SandboxPreset = SandboxPreset.SUCCESS,
        checkpoint_id: str = "",
        is_execution_handle: bool = False,
        execution_presets: Optional[List[SandboxPreset]] = None,
    ):
        self.preset = preset
        self.checkpoint_id = checkpoint_id
        self.is_execution_handle = is_execution_handle
        self.execution_presets: List[SandboxPreset] = (
            list(execution_presets) if execution_presets else []
        )
        self.execution_handles: List["FakeSandboxAdapter"] = []
        self.cleaned_up: bool = False
        self.call_count: int = 0
        self.executed_commands: List[List[str]] = []
        self._upgrade_installed: bool = False
        self._patch_applied: bool = False
        self._tampered: bool = (preset == SandboxPreset.VERIFY_TEST_TAMPERING)
        self.file_hashes: Dict[str, str] = dict(self.DEFAULT_TEST_HASHES)
        self.node_ids: List[str] = list(self.DEFAULT_NODE_IDS)

    async def create_execution(self, checkpoint_id: str) -> "FakeSandboxAdapter":
        """Creates an independent execution sandbox instance from the specified checkpoint."""
        if self.preset == SandboxPreset.EXECUTION_CREATION_FAIL:
            raise RuntimeError(f"Failed to provision execution container from checkpoint '{checkpoint_id}'")
        child_preset = (
            self.execution_presets.pop(0) if self.execution_presets else self.preset
        )
        if child_preset == SandboxPreset.EXECUTION_CREATION_FAIL:
            raise RuntimeError(f"Failed to provision execution container from checkpoint '{checkpoint_id}'")
        child = FakeSandboxAdapter(
            preset=child_preset,
            checkpoint_id=checkpoint_id,
            is_execution_handle=True,
        )
        child._upgrade_installed = True
        child._tampered = (child_preset == SandboxPreset.VERIFY_TEST_TAMPERING)
        child.file_hashes = dict(self.file_hashes)
        child.node_ids = list(self.node_ids)
        self.execution_handles.append(child)
        return child

    async def cleanup(self) -> None:
        """Cleans up isolated execution handle and resources."""
        self.cleaned_up = True

    async def hash_files(
        self, paths_or_patterns: Optional[List[str]] = None
    ) -> Dict[str, str]:
        """Returns hashes of test and configuration files."""
        hashes = dict(self.file_hashes)
        if self._tampered and self._patch_applied:
            hashes["tests/test_app.py"] = "tampered_hash_modified_by_patch_49817294"
        return hashes

    async def execute_command(
        self, command: List[str], timeout_seconds: int = 60
    ) -> CommandResult:
        self.call_count += 1
        self.executed_commands.append(list(command))

        if self.preset == SandboxPreset.TIMEOUT:
            raise TimeoutError(f"Execution timed out after {timeout_seconds} seconds")

        cmd_name = command[0] if command else ""

        # 1. Pytest collection command (--collect-only)
        if any("--collect-only" in arg for arg in command):
            if self.preset == SandboxPreset.VERIFY_NODE_ID_MISMATCH:
                mismatch_ids = ["tests/test_app.py::test_one"]
                return CommandResult(
                    exit_code=0,
                    stdout="tests/test_app.py::test_one\n1 item collected in 0.01s",
                    stderr="",
                    collected_count=1,
                    collected_node_ids=mismatch_ids,
                )
            return CommandResult(
                exit_code=0,
                stdout="\n".join(self.node_ids) + f"\n{len(self.node_ids)} items collected in 0.01s",
                stderr="",
                collected_count=len(self.node_ids),
                collected_node_ids=list(self.node_ids),
            )

        # 2. Dependency upgrade installation command
        if cmd_name == "pip" or (len(command) > 1 and command[1] == "install"):
            if self.preset == SandboxPreset.UPGRADE_INSTALL_FAIL:
                return CommandResult(
                    exit_code=1,
                    stdout="",
                    stderr="ERROR: Could not find a version that satisfies requirement",
                )
            self._upgrade_installed = True
            return CommandResult(
                exit_code=0,
                stdout="Successfully installed package",
                stderr="",
                installed_version="2.0.0",
                import_origin="site-packages",
            )

        # 3. Patch application command
        if cmd_name == "git" and len(command) > 1 and command[1] == "apply":
            if self.preset == SandboxPreset.PATCH_APPLY_FAIL:
                return CommandResult(
                    exit_code=1,
                    stdout="",
                    stderr="error: patch failed: src/app.py:10, patch does not apply",
                )
            self._patch_applied = True
            return CommandResult(
                exit_code=0, stdout="Patch applied cleanly", stderr=""
            )

        # 4. Test execution commands
        if self._patch_applied or self.is_execution_handle:
            # Post-patch verification test
            if self.preset == SandboxPreset.VERIFY_TEST_FAIL:
                return CommandResult(
                    exit_code=1,
                    stdout="",
                    stderr="AssertionError: Candidate patch failed to fix error",
                    collected_count=len(self.node_ids),
                    collected_node_ids=list(self.node_ids),
                )
            if self.preset == SandboxPreset.VERIFY_COLLECTION_MISMATCH:
                return CommandResult(
                    exit_code=0,
                    stdout="collected 1 item, 1 passed",
                    stderr="",
                    collected_count=1,
                    collected_node_ids=["tests/test_app.py::test_one"],
                )
            if self.preset == SandboxPreset.VERIFY_NEW_SKIPS:
                return CommandResult(
                    exit_code=0,
                    stdout="collected 2 items, 1 passed, 1 skipped",
                    stderr="",
                    collected_count=len(self.node_ids),
                    skipped_count=1,
                    collected_node_ids=list(self.node_ids),
                )
            if self.preset == SandboxPreset.VERIFY_VERSION_MISMATCH:
                return CommandResult(
                    exit_code=0,
                    stdout="2 passed in 0.05s",
                    stderr="",
                    collected_count=len(self.node_ids),
                    skipped_count=0,
                    installed_version="0.9.0",  # Mismatch with expected upgrade
                    import_origin="site-packages",
                    collected_node_ids=list(self.node_ids),
                )
            if self.preset == SandboxPreset.VERIFY_IMPORT_ORIGIN_MISMATCH:
                return CommandResult(
                    exit_code=0,
                    stdout="2 passed in 0.05s",
                    stderr="",
                    collected_count=len(self.node_ids),
                    skipped_count=0,
                    installed_version="2.0.0",
                    import_origin="untrusted-local",
                    collected_node_ids=list(self.node_ids),
                )
            if self.preset == SandboxPreset.VERIFY_MISSING_EVIDENCE:
                return CommandResult(
                    exit_code=0,
                    stdout="2 passed in 0.05s",
                    stderr="",
                    collected_count=len(self.node_ids),
                    skipped_count=0,
                    installed_version="",
                    import_origin="",
                    collected_node_ids=list(self.node_ids),
                )
            # Default clean verification
            return CommandResult(
                exit_code=0,
                stdout="2 passed in 0.05s",
                stderr="",
                collected_count=len(self.node_ids),
                skipped_count=0,
                installed_version="2.0.0",
                import_origin="site-packages",
                collected_node_ids=list(self.node_ids),
            )

        if self._upgrade_installed:
            # Post-upgrade failure reproduction test
            if self.preset == SandboxPreset.UPGRADE_FAILURE_NOT_REPRODUCED:
                return CommandResult(
                    exit_code=0,
                    stdout="2 passed in 0.05s",
                    stderr="",
                    collected_count=len(self.node_ids),
                    collected_node_ids=list(self.node_ids),
                )
            if self.preset == SandboxPreset.UPGRADE_UNEXPECTED_FAILURE:
                return CommandResult(
                    exit_code=1,
                    stdout="",
                    stderr="SyntaxError: invalid syntax in test suite",
                    collected_count=len(self.node_ids),
                    collected_node_ids=list(self.node_ids),
                )
            # Default: reproduce expected failure with AssertionError
            return CommandResult(
                exit_code=1,
                stdout=f"collected {len(self.node_ids)} items",
                stderr="AssertionError: target dependency upgrade broke tests",
                collected_count=len(self.node_ids),
                collected_node_ids=list(self.node_ids),
            )

        # 5. Baseline stage checks (before upgrade installed)
        if self.preset == SandboxPreset.FIRST_FAIL:
            if self.call_count == 1:
                return CommandResult(
                    exit_code=1,
                    stdout="",
                    stderr="AssertionError in test suite",
                    collected_count=len(self.node_ids),
                    collected_node_ids=list(self.node_ids),
                )
            return CommandResult(
                exit_code=0,
                stdout="2 passed",
                stderr="",
                collected_count=len(self.node_ids),
                collected_node_ids=list(self.node_ids),
            )

        if self.preset == SandboxPreset.SECOND_FAIL:
            if self.call_count == 1:
                return CommandResult(
                    exit_code=0,
                    stdout="2 passed",
                    stderr="",
                    collected_count=len(self.node_ids),
                    collected_node_ids=list(self.node_ids),
                )
            return CommandResult(
                exit_code=1,
                stdout="",
                stderr="Flaky baseline failure in second check",
                collected_count=len(self.node_ids),
                collected_node_ids=list(self.node_ids),
            )

        if self.preset == SandboxPreset.UNSTABLE_COLLECTION:
            if self.call_count == 1:
                return CommandResult(
                    exit_code=0,
                    stdout="collected 2 items",
                    stderr="",
                    collected_count=2,
                    collected_node_ids=list(self.node_ids),
                )
            return CommandResult(
                exit_code=0,
                stdout="collected 3 items",
                stderr="",
                collected_count=3,
                collected_node_ids=list(self.node_ids) + ["tests/test_app.py::test_three"],
            )

        # Default clean baseline execution
        return CommandResult(
            exit_code=0,
            stdout="2 passed in 0.05s",
            stderr="",
            collected_count=len(self.node_ids),
            collected_node_ids=list(self.node_ids),
        )
