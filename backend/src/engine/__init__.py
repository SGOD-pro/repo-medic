from src.engine.adapters import (
    CommandResult,
    ModelAdapter,
    SandboxAdapter,
    SandboxPreset,
)
from src.engine.baseline import (
    BaselineOutcome,
    record_baseline_preservation,
    run_baseline_stage,
)
from src.engine.branch_search import run_branch_refine_search
from src.engine.candidate import (
    BranchAttempt,
    BranchSearchBudget,
    BranchSearchResult,
    CandidatePatch,
    CandidateVerification,
    EvidenceManifest,
    PatchValidationResult,
    SequentialRepairOutcome,
    TestPreservationRecord,
    UpgradeResult,
    VerificationChecks,
)
from src.engine.candidate_generator import (
    build_refinement_prompt,
    generate_candidate_patch,
    generate_refinement_patch,
)
from src.engine.extraction import extract_error_context
from src.engine.fake_model import FakeModelAdapter
from src.engine.fake_sandbox import FakeSandboxAdapter
from src.engine.token_factory_model import TokenFactoryModelAdapter
from src.engine.patch_validator import parse_modified_files, validate_patch
from src.engine.repair import repair
from src.engine.upgrade import derive_upgrade_command, run_upgrade_stage
from src.engine.validation import RecipeValidationError, validate_recipe
from src.engine.verifier import (
    build_evidence_manifest,
    compare_test_file_hashes,
    parse_pytest_node_ids,
    verify_candidate_patch,
)

__all__ = [
    "repair",
    "run_branch_refine_search",
    "BranchAttempt",
    "BranchSearchBudget",
    "BranchSearchResult",
    "SandboxAdapter",
    "ModelAdapter",
    "CommandResult",
    "SandboxPreset",
    "FakeSandboxAdapter",
    "FakeModelAdapter",
    "TokenFactoryModelAdapter",
    "validate_recipe",
    "RecipeValidationError",
    "run_baseline_stage",
    "record_baseline_preservation",
    "BaselineOutcome",
    "UpgradeResult",
    "CandidatePatch",
    "PatchValidationResult",
    "CandidateVerification",
    "SequentialRepairOutcome",
    "TestPreservationRecord",
    "VerificationChecks",
    "EvidenceManifest",
    "extract_error_context",
    "derive_upgrade_command",
    "run_upgrade_stage",
    "validate_patch",
    "parse_modified_files",
    "generate_candidate_patch",
    "generate_refinement_patch",
    "build_refinement_prompt",
    "verify_candidate_patch",
    "build_evidence_manifest",
    "compare_test_file_hashes",
    "parse_pytest_node_ids",
]
