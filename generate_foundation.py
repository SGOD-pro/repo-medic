import os
import json

# contracts.py
contracts_py = """\
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
"""

# contracts.ts
contracts_ts = """\
export type Mode = "offline" | "replay" | "live";
export type State = "succeeded" | "failed" | "cancelled";

export interface TaskSummary {
  task_id: string;
  repository: string;
  commit: string;
}

export interface TaskRecipe extends TaskSummary {
  test_command: string[];
  allowed_source_paths: string[];
  expected_failure: string;
  timeout_seconds: number;
  max_candidates: number;
  max_refinements: number;
}

export interface RepairRequest {
  run_id: string;
  task_id: string;
  mode: Mode;
  search_mode: string;
  max_run_usd: number;
}

export interface RepairResult {
  state: State;
  reason?: string;
}
"""

os.makedirs('backend/src', exist_ok=True)
os.makedirs('frontend/src/lib', exist_ok=True)
with open('backend/src/contracts.py', 'w') as f:
    f.write(contracts_py)
with open('frontend/src/lib/contracts.ts', 'w') as f:
    f.write(contracts_ts)

# Create fixtures
fixtures_dir = 'fixtures'
os.makedirs(os.path.join(fixtures_dir, 'tasks'), exist_ok=True)
os.makedirs(os.path.join(fixtures_dir, 'runs'), exist_ok=True)
os.makedirs(os.path.join(fixtures_dir, 'providers'), exist_ok=True)

task_recipe = {
    "task_id": "example-task-1",
    "repository": "https://github.com/example/repo",
    "commit": "abcdef123456",
    "test_command": ["pytest", "tests/"],
    "allowed_source_paths": ["src/"],
    "expected_failure": "AssertionError",
    "timeout_seconds": 600,
    "max_candidates": 3,
    "max_refinements": 1
}

with open(f'{fixtures_dir}/tasks/example-task-1.json', 'w') as f:
    json.dump(task_recipe, f, indent=2)

with open(f'{fixtures_dir}/runs/success.json', 'w') as f:
    json.dump({
        "run_id": "run-success-1",
        "task_id": "example-task-1",
        "mode": "offline",
        "search_mode": "sequential",
        "max_run_usd": 10.0,
        "state": "succeeded"
    }, f, indent=2)

