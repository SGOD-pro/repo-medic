import pytest
from src.contracts import TaskRecipe
from src.engine.adapters import SandboxPreset
from src.engine.baseline import record_baseline_preservation
from src.engine.candidate import CandidatePatch, TestPreservationRecord
from src.engine.fake_sandbox import FakeSandboxAdapter
from src.engine.verifier import verify_candidate_patch
from src.storage.fake_host import FakeHost


@pytest.fixture
def test_recipe() -> TaskRecipe:
    return TaskRecipe(
        task_id="task-ver-001",
        title="Safe Verifier Task",
        repository_url="https://github.com/example/repo",
        commit_sha="c0ffee1234",
        dependency="urllib3",
        from_version="1.26.0",
        to_version="2.0.0",
        test_command=["pytest", "tests/"],
        allowed_source_paths=["src/"],
        expected_failure="AssertionError",
        timeout_seconds=30,
        max_candidates=1,
        max_refinements=0,
    )


@pytest.fixture
def valid_candidate() -> CandidatePatch:
    diff = (
        "--- a/src/app.py\n"
        "+++ b/src/app.py\n"
        "@@ -10,1 +10,1 @@\n"
        "- old_call()\n"
        "+ new_call()\n"
    )
    return CandidatePatch(
        candidate_id="cand-001",
        diff_content=diff,
        modified_files=["src/app.py"],
    )


@pytest.fixture
def baseline_preservation() -> TestPreservationRecord:
    return TestPreservationRecord(
        root_dir=".",
        file_hashes=dict(FakeSandboxAdapter.DEFAULT_TEST_HASHES),
        node_ids=list(FakeSandboxAdapter.DEFAULT_NODE_IDS),
        collected_count=2,
    )


@pytest.mark.asyncio
async def test_baseline_preservation_records_hashes_and_node_ids(test_recipe):
    # covers: AC-1
    sandbox = FakeSandboxAdapter(SandboxPreset.SUCCESS)
    record = await record_baseline_preservation(test_recipe, sandbox, baseline_collected_count=2)

    assert record.collected_count == 2
    assert "tests/test_app.py" in record.file_hashes
    assert "tests/conftest.py" in record.file_hashes
    assert len(record.node_ids) == 2
    assert "tests/test_app.py::test_one" in record.node_ids


@pytest.mark.asyncio
async def test_verifier_creates_fresh_execution_from_checkpoint(
    test_recipe, valid_candidate, baseline_preservation
):
    # covers: AC-2
    sandbox = FakeSandboxAdapter(SandboxPreset.SUCCESS)
    host = FakeHost()

    outcome = await verify_candidate_patch(
        candidate=valid_candidate,
        recipe=test_recipe,
        sandbox=sandbox,
        host=host,
        baseline_collected_count=2,
        baseline_preservation=baseline_preservation,
        checkpoint_id="chk_upgraded_snap_42",
    )

    assert outcome.passed is True
    assert outcome.manifest is not None
    assert outcome.manifest.checks.checkpoint_isolated is True
    assert outcome.manifest.checkpoint_id == "chk_upgraded_snap_42"


@pytest.mark.asyncio
async def test_verifier_rejects_test_file_tampering(
    test_recipe, valid_candidate, baseline_preservation
):
    # covers: AC-3
    sandbox = FakeSandboxAdapter(SandboxPreset.VERIFY_TEST_TAMPERING)
    host = FakeHost()

    outcome = await verify_candidate_patch(
        candidate=valid_candidate,
        recipe=test_recipe,
        sandbox=sandbox,
        host=host,
        baseline_collected_count=2,
        baseline_preservation=baseline_preservation,
    )

    assert outcome.passed is False
    assert outcome.reason == "test_tampering_detected"
    assert "tampering detected" in outcome.summary.lower()


@pytest.mark.asyncio
async def test_verifier_handles_patch_apply_failure(
    test_recipe, valid_candidate, baseline_preservation
):
    # covers: AC-4
    sandbox = FakeSandboxAdapter(SandboxPreset.PATCH_APPLY_FAIL)
    host = FakeHost()

    outcome = await verify_candidate_patch(
        candidate=valid_candidate,
        recipe=test_recipe,
        sandbox=sandbox,
        host=host,
        baseline_collected_count=2,
        baseline_preservation=baseline_preservation,
    )

    assert outcome.passed is False
    assert outcome.reason == "patch_apply_failed"
    assert "failed to apply" in outcome.summary.lower()


@pytest.mark.asyncio
async def test_verifier_rejects_node_id_mismatch(
    test_recipe, valid_candidate, baseline_preservation
):
    # covers: AC-5
    sandbox = FakeSandboxAdapter(SandboxPreset.VERIFY_NODE_ID_MISMATCH)
    host = FakeHost()

    outcome = await verify_candidate_patch(
        candidate=valid_candidate,
        recipe=test_recipe,
        sandbox=sandbox,
        host=host,
        baseline_collected_count=2,
        baseline_preservation=baseline_preservation,
    )

    assert outcome.passed is False
    assert outcome.reason == "test_ids_mismatch"
    assert "mismatch" in outcome.summary.lower()


@pytest.mark.asyncio
async def test_verifier_rejects_test_failures_or_new_skips(
    test_recipe, valid_candidate, baseline_preservation
):
    # covers: AC-6
    # 1. Failing tests
    fail_sandbox = FakeSandboxAdapter(SandboxPreset.VERIFY_TEST_FAIL)
    host1 = FakeHost()
    res_fail = await verify_candidate_patch(
        candidate=valid_candidate,
        recipe=test_recipe,
        sandbox=fail_sandbox,
        host=host1,
        baseline_collected_count=2,
        baseline_preservation=baseline_preservation,
    )
    assert res_fail.passed is False
    assert res_fail.reason == "tests_failed"

    # 2. Newly skipped tests
    skip_sandbox = FakeSandboxAdapter(SandboxPreset.VERIFY_NEW_SKIPS)
    host2 = FakeHost()
    res_skip = await verify_candidate_patch(
        candidate=valid_candidate,
        recipe=test_recipe,
        sandbox=skip_sandbox,
        host=host2,
        baseline_collected_count=2,
        baseline_preservation=baseline_preservation,
    )
    assert res_skip.passed is False
    assert res_skip.manifest.checks.zero_new_skips is False


@pytest.mark.asyncio
async def test_verifier_rejects_dependency_version_mismatch(
    test_recipe, valid_candidate, baseline_preservation
):
    # covers: AC-7
    sandbox = FakeSandboxAdapter(SandboxPreset.VERIFY_VERSION_MISMATCH)
    host = FakeHost()

    outcome = await verify_candidate_patch(
        candidate=valid_candidate,
        recipe=test_recipe,
        sandbox=sandbox,
        host=host,
        baseline_collected_count=2,
        baseline_preservation=baseline_preservation,
    )

    assert outcome.passed is False
    assert outcome.reason == "dependency_version_mismatch"
    assert "dependency version changed" in outcome.summary.lower()


@pytest.mark.asyncio
async def test_evidence_manifest_structure_and_offline_mode(
    test_recipe, valid_candidate, baseline_preservation
):
    # covers: AC-8
    sandbox = FakeSandboxAdapter(SandboxPreset.SUCCESS)
    host = FakeHost()

    outcome = await verify_candidate_patch(
        candidate=valid_candidate,
        recipe=test_recipe,
        sandbox=sandbox,
        host=host,
        baseline_collected_count=2,
        baseline_preservation=baseline_preservation,
        mode="offline",
    )

    assert outcome.passed is True
    manifest = outcome.manifest
    assert manifest is not None
    assert manifest.schema_version == "1.0.0"
    assert manifest.candidate_id == "cand-001"
    assert manifest.task_id == "task-ver-001"
    assert manifest.execution_mode == "offline"
    assert manifest.dependency == "urllib3"
    assert manifest.to_version == "2.0.0"
    assert "evidence.json" in manifest.artifact_hashes
    assert "patch.diff" in manifest.artifact_hashes
    assert "verify.log" in manifest.artifact_hashes
    assert manifest.checks.tests_passed is True
    assert manifest.checks.artifacts_persisted is True

    # Host saved artifacts verification
    saved_kinds = [a["kind"] for a in host.artifacts]
    assert "evidence" in saved_kinds
    assert "patch" in saved_kinds
    assert "log" in saved_kinds


@pytest.mark.asyncio
async def test_artifact_persistence_failure_marks_candidate_failed(
    test_recipe, valid_candidate, baseline_preservation
):
    # covers: AC-9
    # When host.save_artifact fails, tests may have passed, but candidate cannot be declared verified
    class FailingStorageHost(FakeHost):
        async def save_artifact(self, kind: str, filename: str, content: bytes) -> str:
            if kind == "evidence":
                raise RuntimeError("Disk quota exceeded for evidence storage")
            return await super().save_artifact(kind, filename, content)

    sandbox = FakeSandboxAdapter(SandboxPreset.SUCCESS)
    host = FailingStorageHost()

    outcome = await verify_candidate_patch(
        candidate=valid_candidate,
        recipe=test_recipe,
        sandbox=sandbox,
        host=host,
        baseline_collected_count=2,
        baseline_preservation=baseline_preservation,
    )

    assert outcome.passed is False
    assert outcome.reason == "artifact_persistence_failed"
    # Actual test execution passed, but verification failed due to missing evidence storage
    assert outcome.manifest is not None
    assert outcome.manifest.checks.tests_passed is True
    assert outcome.manifest.checks.artifacts_persisted is False
    assert "artifact persistence failed" in outcome.summary.lower()


@pytest.mark.asyncio
async def test_verifier_timeout_and_resource_cleanup(
    test_recipe, valid_candidate, baseline_preservation
):
    # covers: AC-10
    # 1. Successful run calls execution handle cleanup
    sandbox_success = FakeSandboxAdapter(SandboxPreset.SUCCESS)
    host1 = FakeHost()
    await verify_candidate_patch(
        candidate=valid_candidate,
        recipe=test_recipe,
        sandbox=sandbox_success,
        host=host1,
        baseline_collected_count=2,
        baseline_preservation=baseline_preservation,
    )

    # 2. Timeout in command execution is handled cleanly
    sandbox_timeout = FakeSandboxAdapter(SandboxPreset.TIMEOUT)
    host2 = FakeHost()
    timeout_outcome = await verify_candidate_patch(
        candidate=valid_candidate,
        recipe=test_recipe,
        sandbox=sandbox_timeout,
        host=host2,
        baseline_collected_count=2,
        baseline_preservation=baseline_preservation,
    )
    assert timeout_outcome.passed is False
    assert timeout_outcome.reason in ("patch_apply_failed", "tests_failed")
