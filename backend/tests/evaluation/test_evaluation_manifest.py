from pathlib import Path
import pytest
from src.evaluation.manifest import load_evaluation_manifest


def test_load_evaluation_manifest():
    manifest = load_evaluation_manifest()
    assert manifest.manifest_version == "1.0.0"
    assert manifest.spending_caps["global_budget_ceiling_usd"] == 25.00
    assert manifest.history_classification is not None
    assert len(manifest.scenarios) == 3

    # Scenario 1: controlled sequential migration
    s1 = manifest.scenarios[0]
    assert s1.task_id == "TASK-091"
    assert s1.search_mode == "sequential"
    assert s1.execution_status == "succeeded"
    assert len(s1.attempts) == 6
    succ = s1.attempts[-1]
    assert succ["state"] == "succeeded"
    assert succ["run_id"] == "run_k4_live_1792870515"
    assert succ["model_calls"] == 1
    assert "token_telemetry" in succ
    assert succ["estimated_allocation_usd"] == 0.35
    assert succ["verification_outcome"]["verified_version"] == "2.0.19"
    assert succ["verification_outcome"]["tests_passed"] is True
    recipe1 = s1.to_task_recipe()
    assert recipe1.task_id == "TASK-091"

    # Scenario 2: accessible external project at verified full commit
    s2 = manifest.scenarios[1]
    assert s2.task_id == "TASK-092"
    assert s2.search_mode == "sequential"
    assert s2.execution_status == "pending_execution"
    assert s2.target.repository_url == "https://github.com/encode/databases.git"
    assert len(s2.target.commit_sha) == 40
    assert s2.target.commit_sha == "6b0c767588f501d5edaabb1bdf665fcf1ded88ea"
    assert s2.target.spending_cap_usd == 2.00
    recipe2 = s2.to_task_recipe()
    assert recipe2.dependency == "sqlalchemy"
    assert recipe2.from_version == "1.4.42"
    assert recipe2.expected_failure == "AttributeError: type object 'Row' has no attribute '_default_key_style'"
    assert recipe2.test_command == [
        "env",
        "TEST_DATABASE_URLS=sqlite:///testsuite,sqlite+aiosqlite:///testsuite",
        "pytest",
        "tests/test_databases.py",
    ]
    assert len(s2.attempts) == 0

    # Scenario 3: bounded live branch and refine scenario
    s3 = manifest.scenarios[2]
    assert s3.task_id == "TASK-093"
    assert s3.search_mode == "branch_refine"
    assert s3.execution_status == "pending_execution"
    assert len(s3.target.commit_sha) == 40
    assert s3.target.spending_cap_usd == 2.00
    recipe3 = s3.to_task_recipe()
    assert recipe3.max_candidates == 3
    assert recipe3.max_refinements == 1
    assert len(s3.attempts) == 0
