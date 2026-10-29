from pydantic import BaseModel, Field, model_validator
from typing import List, Optional, Literal, Protocol, Dict, Any, Union


# Mode and state literals matching API.md
Mode = Literal["offline", "replay", "live"]
SearchMode = Literal["sequential", "branch_refine"]
RunState = Literal["queued", "running", "succeeded", "failed", "cancelled"]
TerminalRunState = Literal["succeeded", "failed", "cancelled"]
ArtifactKind = Literal["patch", "evidence", "log"]
StageName = Literal["baseline", "upgrade", "repair", "verification"]

SUPPORTED_DEMO_TASK_IDS: tuple[str, ...] = (
    "TASK-DEMO-SHOP",
    "TASK-091",
    "TASK-DEMO-PYDANTIC",
    "TASK-DEMO-CLICK",
)


class CustomRepositoryConfig(BaseModel):
    repository_url: str
    commit_sha: str
    dependency: str
    from_version: str
    to_version: str
    pytest_args: List[str]
    allowed_source_paths: List[str]
    expected_failure: str


class CustomConfigValidationResponse(BaseModel):
    valid: bool
    errors: List[str] = Field(default_factory=list)
    field_errors: Dict[str, List[str]] = Field(default_factory=dict)
    custom_execution_supported: bool = False
    gate_status: str = "disabled"
    gate_message: str = (
        "Custom repository execution is disabled in this safe product slice. "
        "Arbitrary remote execution, background worker enqueueing, provider calls, "
        "and task execution are strictly gated off."
    )



class TaskSummary(BaseModel):
    task_id: str
    title: str
    repository_url: str
    commit_sha: str
    dependency: str
    from_version: str
    to_version: str


class TaskRecipe(TaskSummary):
    test_command: List[str]
    allowed_source_paths: List[str]
    expected_failure: str
    timeout_seconds: int
    max_candidates: int
    max_refinements: int


class ArtifactSummary(BaseModel):
    artifact_id: str
    kind: ArtifactKind
    filename: str


class UsageSummary(BaseModel):
    model_calls: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    estimated_usd: float = Field(ge=0.0)


class RunSummary(BaseModel):
    run_id: str
    task_id: str
    mode: Mode
    search_mode: SearchMode
    state: RunState
    reason: str | None = None
    created_at: str | None = None
    max_run_micro_usd: int | None = 0
    usage: UsageSummary
    artifacts: list[ArtifactSummary] = Field(default_factory=list)


# Backward compatible alias for tests using RunDetail
RunDetail = RunSummary


class RunHistoryItem(BaseModel):
    run_id: str
    state: RunState


class RepairRequest(BaseModel):
    run_id: str
    task_id: str
    mode: Mode
    search_mode: SearchMode
    max_run_usd: float = Field(ge=0.0)


class RepairResult(BaseModel):
    state: TerminalRunState
    reason: Optional[str] = None


# Typed Event Payloads
class RunStartedPayload(BaseModel):
    mode: Mode
    search_mode: SearchMode
    max_run_usd: float = Field(ge=0.0)


class StageCompletedPayload(BaseModel):
    stage: StageName
    passed: bool
    summary: str


class CandidateCompletedPayload(BaseModel):
    candidate_id: str
    passed: bool
    summary: str


class RunFinishedPayload(BaseModel):
    state: TerminalRunState
    reason: Optional[str] = None


EventType = Literal[
    "run.started",
    "stage.completed",
    "candidate.completed",
    "usage.updated",
    "run.finished",
]


class EventEnvelope(BaseModel):
    run_id: str
    seq: int = Field(ge=1)
    ts: str
    type: EventType
    payload: Dict[str, Any]

    @model_validator(mode="after")
    def validate_payload_by_type(self) -> "EventEnvelope":
        if not isinstance(self.payload, dict) or not self.payload:
            raise ValueError(f"Payload for event '{self.type}' cannot be empty")
        if self.type == "run.started":
            RunStartedPayload.model_validate(self.payload)
        elif self.type == "stage.completed":
            StageCompletedPayload.model_validate(self.payload)
        elif self.type == "candidate.completed":
            CandidateCompletedPayload.model_validate(self.payload)
        elif self.type == "usage.updated":
            UsageSummary.model_validate(self.payload)
        elif self.type == "run.finished":
            RunFinishedPayload.model_validate(self.payload)
        else:
            raise ValueError(f"Unsupported event type: {self.type}")
        return self


Event = EventEnvelope


class ReconnectResult(BaseModel):
    run_id: str
    events: List[EventEnvelope]


class ErrorDetail(BaseModel):
    code: str
    message: str


class APIErrorEnvelope(BaseModel):
    error: ErrorDetail


class HostPorts(Protocol):
    async def emit(self, event_type: str, payload: dict[str, Any]) -> None: ...
    async def save_artifact(self, kind: str, filename: str, content: bytes) -> str: ...
    async def reserve(self, operation_id: str, estimated_usd: float) -> bool: ...
    async def settle(self, operation_id: str, actual_or_estimated_usd: float) -> None: ...
    async def cancelled(self) -> bool: ...
    async def record_provider_ref(self, operation_id: str, provider_ref: str) -> None: ...
