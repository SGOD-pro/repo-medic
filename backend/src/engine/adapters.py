from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Protocol


class SandboxPreset(str, Enum):
    SUCCESS = "success"
    FIRST_FAIL = "first_fail"
    SECOND_FAIL = "second_fail"
    UNSTABLE_COLLECTION = "unstable_collection"
    TIMEOUT = "timeout"
    UPGRADE_INSTALL_FAIL = "upgrade_install_fail"
    UPGRADE_FAILURE_NOT_REPRODUCED = "upgrade_failure_not_reproduced"
    UPGRADE_UNEXPECTED_FAILURE = "upgrade_unexpected_failure"
    PATCH_APPLY_FAIL = "patch_apply_fail"
    VERIFY_TEST_FAIL = "verify_test_fail"
    VERIFY_COLLECTION_MISMATCH = "verify_collection_mismatch"
    VERIFY_NEW_SKIPS = "verify_new_skips"
    VERIFY_TEST_TAMPERING = "verify_test_tampering"
    VERIFY_NODE_ID_MISMATCH = "verify_node_id_mismatch"
    VERIFY_VERSION_MISMATCH = "verify_version_mismatch"


@dataclass(frozen=True)
class CommandResult:
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    collected_count: int = 0
    skipped_count: int = 0
    xfailed_count: int = 0
    installed_version: str = ""
    collected_node_ids: List[str] = field(default_factory=list)


class SandboxAdapter(Protocol):
    async def execute_command(
        self, command: List[str], timeout_seconds: int = 60
    ) -> CommandResult: ...

    async def create_execution(
        self, checkpoint_id: str
    ) -> "SandboxAdapter": ...

    async def cleanup(self) -> None: ...

    async def hash_files(
        self, paths_or_patterns: Optional[List[str]] = None
    ) -> Dict[str, str]: ...


class ModelAdapter(Protocol):
    async def complete(self, prompt: str, max_tokens: int = 2048) -> str: ...
