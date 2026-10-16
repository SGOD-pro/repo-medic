from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional
from src.contracts import TerminalRunState


@dataclass(frozen=True)
class UpgradeResult:
    """Outcome of dependency upgrade and failure reproduction attempt."""

    success: bool
    installed_version: str = ""
    failure_output: str = ""
    exit_code: int = 0
    failure_reproduced: bool = False
    summary: str = ""
    checkpoint_id: str = "chk_upgrade"


@dataclass(frozen=True)
class CandidatePatch:
    """Candidate code repair patch proposed by the model."""

    candidate_id: str
    diff_content: str
    modified_files: List[str] = field(default_factory=list)
    raw_model_response: str = ""


@dataclass(frozen=True)
class PatchValidationResult:
    """Security and syntax validation result for a candidate patch."""

    valid: bool
    reason: str = ""
    violations: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class TestPreservationRecord:
    """Baseline record of preserved test files, configuration hashes, and test node IDs."""

    __test__ = False
    root_dir: str = ""
    file_hashes: Dict[str, str] = field(default_factory=dict)
    node_ids: List[str] = field(default_factory=list)
    collected_count: int = 0


@dataclass(frozen=True)
class VerificationChecks:
    """Fine-grained status of each safety and correctness verification check."""

    checkpoint_isolated: bool = False
    pre_patch_hash_match: bool = False
    patch_applied: bool = False
    post_patch_hash_match: bool = False
    collection_node_ids_match: bool = False
    tests_passed: bool = False
    zero_new_skips: bool = False
    post_test_hash_match: bool = False
    version_intact: bool = False
    artifacts_persisted: bool = False


@dataclass(frozen=True)
class EvidenceManifest:
    """Auditable structured evidence manifest saved to evidence.json."""

    schema_version: str = "1.0.0"
    candidate_id: str = ""
    task_id: str = ""
    commit_hash: str = ""
    dependency: str = ""
    from_version: str = ""
    to_version: str = ""
    verified_version: str = ""
    import_origin: str = ""
    checkpoint_id: str = ""
    execution_mode: str = "offline"  # "offline" | "live"
    checks: VerificationChecks = field(default_factory=VerificationChecks)
    test_summary: Dict[str, Any] = field(default_factory=dict)
    artifact_hashes: Dict[str, str] = field(default_factory=dict)
    duration_seconds: float = 0.0
    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CandidateVerification:
    """Execution verification outcome for a candidate patch in the sandbox."""

    candidate_id: str
    passed: bool
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    collected_count: int = 0
    skipped_count: int = 0
    xfailed_count: int = 0
    installed_version: str = ""
    import_origin: str = ""
    summary: str = ""
    duration_seconds: float = 0.0
    reason: Optional[str] = None
    manifest: Optional[EvidenceManifest] = None


@dataclass(frozen=True)
class SequentialRepairOutcome:
    """Overall outcome of the sequential repair workflow."""

    state: TerminalRunState
    reason: Optional[str] = None
    candidate: Optional[CandidatePatch] = None
    verification: Optional[CandidateVerification] = None
    upgrade: Optional[UpgradeResult] = None


@dataclass(frozen=True)
class BranchAttempt:
    """Record of a single candidate or refinement attempt in tree search."""

    attempt_id: str
    branch_index: int
    is_refinement: bool
    parent_candidate_id: Optional[str] = None
    patch: Optional[CandidatePatch] = None
    validation: Optional[PatchValidationResult] = None
    verification: Optional[CandidateVerification] = None
    duration_seconds: float = 0.0


@dataclass(frozen=True)
class BranchSearchBudget:
    """Configured bounds and cost estimates for branch and refine search."""

    max_candidates: int = 3
    max_refinements: int = 1
    estimated_cost_per_generation: float = 0.0


@dataclass(frozen=True)
class BranchSearchResult:
    """Overall outcome of bounded branch and refine search."""

    state: TerminalRunState
    reason: Optional[str] = None
    winning_attempt: Optional[BranchAttempt] = None
    attempts: List[BranchAttempt] = field(default_factory=list)
    total_candidates_generated: int = 0
    total_refinements_generated: int = 0
