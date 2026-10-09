from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Protocol
from datetime import datetime

class TaskSummary(BaseModel):
    task_id: str
    repository: str
    commit: str

class TaskRecipe(TaskSummary):
    test_command: List[str]
    allowed_source_paths: List[str]
    expected_failure: str
    timeout_seconds: int
    max_candidates: int
    max_refinements: int

class RepairRequest(BaseModel):
    run_id: str
    task_id: str
    mode: Literal["offline", "replay", "live"]
    search_mode: str
    max_run_usd: float

class RepairResult(BaseModel):
    state: Literal["succeeded", "failed", "cancelled"]
    reason: Optional[str] = None

class HostPorts(Protocol):
    async def emit(self, event_type: str, payload: dict) -> None: ...
    async def save_artifact(self, kind: str, filename: str, content: bytes) -> str: ...
    async def reserve(self, operation_id: str, estimated_usd: float) -> bool: ...
    async def settle(self, operation_id: str, actual_or_estimated_usd: float) -> None: ...
    async def cancelled(self) -> bool: ...
    async def record_provider_ref(self, operation_id: str, provider_ref: str) -> None: ...
