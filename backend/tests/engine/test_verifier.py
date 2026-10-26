import pytest
from src.contracts import TaskRecipe
from src.engine.adapters import CommandResult, SandboxPreset
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
    assert "evidence.json" not in manifest.artifact_hashes
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


@pytest.mark.asyncio
async def test_verifier_fails_when_fresh_execution_cannot_be_created(
    test_recipe, valid_candidate, baseline_preservation
):
    sandbox = FakeSandboxAdapter(SandboxPreset.EXECUTION_CREATION_FAIL)
    host = FakeHost()

    outcome = await verify_candidate_patch(
        candidate=valid_candidate,
        recipe=test_recipe,
        sandbox=sandbox,
        host=host,
        baseline_collected_count=2,
        baseline_preservation=baseline_preservation,
        checkpoint_id="chk_missing",
    )

    assert outcome.passed is False
    assert outcome.reason == "execution_creation_failed"
    assert "Failed to create fresh execution" in outcome.summary
    assert outcome.manifest is not None
    assert outcome.manifest.checks.checkpoint_isolated is False


@pytest.mark.asyncio
async def test_verifier_fails_on_missing_installed_version_without_substitution(
    test_recipe, valid_candidate, baseline_preservation
):
    sandbox = FakeSandboxAdapter(SandboxPreset.VERIFY_MISSING_EVIDENCE)
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
    assert outcome.reason == "missing_dependency_evidence"
    assert outcome.installed_version == ""
    assert outcome.manifest is not None
    assert outcome.manifest.verified_version == ""
    assert outcome.manifest.verified_version != test_recipe.to_version


@pytest.mark.asyncio
async def test_verifier_fails_on_untrusted_import_origin(
    test_recipe, valid_candidate, baseline_preservation
):
    sandbox = FakeSandboxAdapter(SandboxPreset.VERIFY_IMPORT_ORIGIN_MISMATCH)
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
    assert outcome.reason == "invalid_import_origin"
    assert "untrusted or invalid dependency import-origin" in outcome.summary


@pytest.mark.asyncio
async def test_verifier_preserves_baseline_skips_and_xfails(test_recipe, valid_candidate):
    """Verify that baseline skips and xfails are preserved, and only newly added skips/xfails fail."""
    from src.engine.candidate import TestPreservationRecord

    class SkipSandbox(FakeSandboxAdapter):
        def __init__(self, skips: int, xfails: int, **kwargs):
            super().__init__(**kwargs)
            self.simulated_skips = skips
            self.simulated_xfails = xfails

        async def create_execution(self, checkpoint_id: str):
            await super().create_execution(checkpoint_id)
            child = SkipSandbox(skips=self.simulated_skips, xfails=self.simulated_xfails, is_execution_handle=True)
            child.file_hashes = dict(self.file_hashes)
            child.node_ids = list(self.node_ids)
            return child

        async def execute_command(self, command, timeout_seconds=60):
            res = await super().execute_command(command, timeout_seconds=timeout_seconds)
            if any("--collect-only" in arg for arg in command):
                return res
            # Return tests with simulated baseline skips and xfails
            return CommandResult(
                exit_code=0,
                stdout=f"68 passed, {self.simulated_skips} skipped, {self.simulated_xfails} xfailed in 1.0s",
                stderr="",
                collected_count=78,
                skipped_count=self.simulated_skips,
                xfailed_count=self.simulated_xfails,
                installed_version="2.0.0",
                import_origin="site-packages",
                collected_node_ids=list(self.node_ids),
            )

    # 1. Baseline had 10 skips and 2 xfails. Current run has exact same 10 skips and 2 xfails.
    sandbox1 = SkipSandbox(skips=10, xfails=2)
    preservation = TestPreservationRecord(
        root_dir=".",
        file_hashes=dict(sandbox1.file_hashes),
        node_ids=list(sandbox1.node_ids),
        collected_count=78,
        skipped_count=10,
        xfailed_count=2,
    )

    host1 = FakeHost()
    outcome1 = await verify_candidate_patch(
        candidate=valid_candidate,
        recipe=test_recipe,
        sandbox=sandbox1,
        host=host1,
        baseline_collected_count=78,
        baseline_preservation=preservation,
    )
    assert outcome1.passed is True
    assert outcome1.manifest.checks.zero_new_skips is True

    # 2. Baseline had 10 skips. Current run has 11 skips (1 newly skipped test).
    host2 = FakeHost()
    sandbox2 = SkipSandbox(skips=11, xfails=2)
    outcome2 = await verify_candidate_patch(
        candidate=valid_candidate,
        recipe=test_recipe,
        sandbox=sandbox2,
        host=host2,
        baseline_collected_count=78,
        baseline_preservation=preservation,
    )
    assert outcome2.passed is False
    assert outcome2.manifest.checks.zero_new_skips is False
    assert "1 newly skipped tests detected" in outcome2.summary

    # 3. Baseline had 2 xfails. Current run has 3 xfails (1 newly xfailed test).
    host3 = FakeHost()
    sandbox3 = SkipSandbox(skips=10, xfails=3)
    outcome3 = await verify_candidate_patch(
        candidate=valid_candidate,
        recipe=test_recipe,
        sandbox=sandbox3,
        host=host3,
        baseline_collected_count=78,
        baseline_preservation=preservation,
    )
    assert outcome3.passed is False
    assert "1 newly xfailed tests detected" in outcome3.summary


@pytest.mark.asyncio
async def test_verifier_wrapped_env_pytest_command_identities_and_verification(valid_candidate):
    """Verify that wrapped env/pytest commands produce test identities and verify full suite correctly."""
    from src.engine.candidate import TestPreservationRecord

    wrapped_recipe = TaskRecipe(
        task_id="TASK-092",
        title="sqlalchemy v1.4.42 to v2.0.19 in encode/databases external project",
        repository_url="https://github.com/encode/databases.git",
        commit_sha="6b0c767588f501d5edaabb1bdf665fcf1ded88ea",
        dependency="sqlalchemy",
        from_version="1.4.42",
        to_version="2.0.19",
        test_command=[
            "env",
            "TEST_DATABASE_URLS=sqlite:///testsuite",
            "pytest",
            "tests/test_databases.py",
        ],
        allowed_source_paths=["databases/core.py", "databases/backends/sqlite.py"],
        expected_failure="AttributeError",
        timeout_seconds=600,
        max_candidates=3,
        max_refinements=1,
    )

    class WrappedSandbox(FakeSandboxAdapter):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.node_ids = ["tests/test_databases.py::test_queries", "tests/test_databases.py::test_sqlite"]

        async def create_execution(self, checkpoint_id: str):
            await super().create_execution(checkpoint_id)
            child = WrappedSandbox(is_execution_handle=True)
            child.file_hashes = dict(self.file_hashes)
            child.node_ids = list(self.node_ids)
            return child

        async def execute_command(self, command, timeout_seconds=60):
            await super().execute_command(command, timeout_seconds=timeout_seconds)
            # Ensure wrapped env is maintained in collect command
            if any("--collect-only" in arg for arg in command):
                assert command[0] == "env"
                assert "TEST_DATABASE_URLS=sqlite:///testsuite" in command[1]
                assert "--collect-only" in command
                return CommandResult(
                    exit_code=0,
                    stdout="\n".join(self.node_ids) + "\n2 items collected",
                    stderr="",
                    collected_count=2,
                    collected_node_ids=list(self.node_ids),
                )
            # Full suite verification execution
            assert command[0] == "env"
            assert command[2] == "pytest"
            return CommandResult(
                exit_code=0,
                stdout="2 passed in 0.5s",
                stderr="",
                collected_count=2,
                skipped_count=0,
                installed_version="2.0.19",
                import_origin="site-packages",
                collected_node_ids=list(self.node_ids),
            )

    sandbox = WrappedSandbox()
    preservation = TestPreservationRecord(
        root_dir=".",
        file_hashes=dict(sandbox.file_hashes),
        node_ids=["tests/test_databases.py::test_queries", "tests/test_databases.py::test_sqlite"],
        collected_count=2,
        skipped_count=0,
        xfailed_count=0,
    )
    host = FakeHost()

    outcome = await verify_candidate_patch(
        candidate=valid_candidate,
        recipe=wrapped_recipe,
        sandbox=sandbox,
        host=host,
        baseline_collected_count=2,
        baseline_preservation=preservation,
    )

    assert outcome.passed is True
    assert outcome.manifest.checks.collection_node_ids_match is True
    assert outcome.manifest.checks.tests_passed is True
    assert outcome.manifest.verified_version == "2.0.19"
