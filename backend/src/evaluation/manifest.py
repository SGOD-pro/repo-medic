import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from src.contracts import SearchMode, TaskRecipe


class ScenarioTarget(BaseModel):
    repository_url: str
    commit_sha: str
    dependency: str
    from_version: str
    to_version: str
    test_command: List[str]
    allowed_source_paths: List[str]
    expected_failure: str
    timeout_seconds: int = 600
    spending_cap_usd: float = 2.00
    max_candidates: int = 3
    max_refinements: int = 1


class EvaluationScenario(BaseModel):
    task_id: str
    name: str
    search_mode: SearchMode
    target: ScenarioTarget
    execution_status: str
    attempts: List[Dict[str, Any]] = Field(default_factory=list)

    def to_task_recipe(self) -> TaskRecipe:
        return TaskRecipe(
            task_id=self.task_id,
            title=self.name,
            repository_url=self.target.repository_url,
            commit_sha=self.target.commit_sha,
            dependency=self.target.dependency,
            from_version=self.target.from_version,
            to_version=self.target.to_version,
            test_command=self.target.test_command,
            allowed_source_paths=self.target.allowed_source_paths,
            expected_failure=self.target.expected_failure,
            timeout_seconds=self.target.timeout_seconds,
            max_candidates=self.target.max_candidates,
            max_refinements=self.target.max_refinements,
        )


class EvaluationManifest(BaseModel):
    manifest_version: str
    created_at: str
    history_classification: Optional[str] = None
    spending_caps: Dict[str, Any]
    scenarios: List[EvaluationScenario]


def load_evaluation_manifest(path: Optional[Path] = None) -> EvaluationManifest:
    if path is None:
        # Default to repo root fixtures/evaluation_manifest.json
        candidate = Path(__file__).resolve().parent.parent.parent.parent / "fixtures" / "evaluation_manifest.json"
        if not candidate.exists():
            candidate = Path("fixtures/evaluation_manifest.json").resolve()
        path = candidate

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return EvaluationManifest.model_validate(data)
