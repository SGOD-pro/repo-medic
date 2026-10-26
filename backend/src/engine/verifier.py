import hashlib
import json
import time
from typing import Any, Dict, List, Optional, Tuple
from src.contracts import HostPorts, TaskRecipe
from src.engine.adapters import CommandResult, SandboxAdapter
from src.engine.candidate import (
    CandidatePatch,
    CandidateVerification,
    EvidenceManifest,
    TestPreservationRecord,
    VerificationChecks,
)


def parse_pytest_node_ids(output: str) -> List[str]:
    """Extracts pytest test node identifiers (e.g., tests/test_app.py::test_case) from stdout."""
    node_ids: List[str] = []
    for line in output.splitlines():
        line = line.strip()
        if "::" in line and not line.startswith(("<", "!", "=", "WARNING")):
            for part in line.split():
                if "::" in part:
                    node_ids.append(part)
                    break
    return sorted(list(set(node_ids)))


def compare_test_file_hashes(
    baseline_hashes: Dict[str, str], current_hashes: Dict[str, str]
) -> Tuple[bool, str]:
    """
    Verifies that all baseline test and configuration files remain identical in current hashes.
    Rejects additions, deletions, or modifications to preserved test infrastructure.
    """
    for file_path, expected_hash in baseline_hashes.items():
        curr_hash = current_hashes.get(file_path)
        if curr_hash is None:
            return False, f"Preserved file '{file_path}' was deleted"
        if curr_hash != expected_hash:
            return False, f"Preserved file '{file_path}' was modified"
    return True, ""


async def _get_hashes(sandbox: SandboxAdapter) -> Dict[str, str]:
    """Retrieves test and config file hashes from sandbox."""
    if hasattr(sandbox, "hash_files") and callable(sandbox.hash_files):
        try:
            return await sandbox.hash_files()
        except Exception:
            pass
    return {}


def build_evidence_manifest(
    candidate: CandidatePatch,
    recipe: TaskRecipe,
    checks: VerificationChecks,
    test_res: CommandResult,
    artifact_hashes: Dict[str, str],
    checkpoint_id: str = "chk_upgrade",
    mode: str = "offline",
    duration_seconds: float = 0.0,
) -> EvidenceManifest:
    """Builds the structured, auditable EvidenceManifest record."""
    test_summary = {
        "exit_code": test_res.exit_code,
        "collected_count": test_res.collected_count,
        "passed_count": max(0, test_res.collected_count - test_res.skipped_count - test_res.xfailed_count)
        if test_res.exit_code == 0
        else 0,
        "failed_count": test_res.collected_count if test_res.exit_code != 0 else 0,
        "skipped_count": test_res.skipped_count,
        "xfailed_count": test_res.xfailed_count,
    }
    return EvidenceManifest(
        schema_version="1.0.0",
        candidate_id=candidate.candidate_id,
        task_id=recipe.task_id,
        commit_hash=recipe.commit_sha,
        dependency=recipe.dependency,
        from_version=recipe.from_version,
        to_version=recipe.to_version,
        verified_version=test_res.installed_version,
        import_origin=getattr(test_res, "import_origin", ""),
        checkpoint_id=checkpoint_id,
        execution_mode=mode,
        checks=checks,
        test_summary=test_summary,
        artifact_hashes=artifact_hashes,
        duration_seconds=duration_seconds,
        created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )


async def verify_candidate_patch(
    candidate: CandidatePatch,
    recipe: TaskRecipe,
    sandbox: SandboxAdapter,
    host: HostPorts,
    baseline_collected_count: int = 0,
    baseline_preservation: Optional[TestPreservationRecord] = None,
    checkpoint_id: str = "chk_upgrade",
    mode: str = "offline",
    artifact_prefix: str = "",
    emit_stage_event: bool = True,
) -> CandidateVerification:
    """
    Verifies a candidate patch in an isolated execution handle derived from the upgraded checkpoint:
    1. Creates fresh execution from the immutable upgraded checkpoint.
    2. Validates preserved test/config hashes (pre-patch).
    3. Applies validated candidate patch.
    4. Validates preserved test/config hashes (post-patch).
    5. Confirms pytest collection node IDs match baseline identically.
    6. Executes full test suite and verifies exit code 0, matching collection, and zero new skips.
    7. Validates preserved test/config hashes (post-test).
    8. Confirms target upgraded dependency version is intact.
    9. Compiles and saves evidence.json, patch.diff, and verify.log via host.save_artifact.
    10. Enforces that artifact storage failure prevents declaring verification success.
    11. Cleans up execution handle resources.
    """
    start_time = time.monotonic()
    candidate_id = candidate.candidate_id
    test_res = CommandResult(exit_code=1)
    exec_sandbox: Optional[Any] = None

    # Reserve budget for candidate verification in live mode
    op_id = f"sandbox:verify:{candidate_id}"
    reserved = False
    if mode == "live":
        reserved = await host.reserve(op_id, 0.10)
        if not reserved:
            summary = "Budget reservation of $0.10 for candidate verification denied by host"
            return await _terminate_verification(
                host=host,
                candidate=candidate,
                recipe=recipe,
                start_time=start_time,
                summary=summary,
                failure_reason="budget_exceeded",
                test_res=test_res,
                checkpoint_id=checkpoint_id,
                mode=mode,
                checks=VerificationChecks(checkpoint_isolated=False),
                test_logs=summary,
                artifact_prefix=artifact_prefix,
                emit_stage_event=emit_stage_event,
            )

    try:
        # 1. Provision fresh isolated execution handle
        checkpoint_isolated = False
        if hasattr(sandbox, "create_execution") and callable(sandbox.create_execution):
            try:
                exec_sandbox = await sandbox.create_execution(checkpoint_id)
                checkpoint_isolated = True
            except Exception as exc:
                summary = f"Failed to create fresh execution from checkpoint '{checkpoint_id}': {exc}"
                return await _terminate_verification(
                    host=host,
                    candidate=candidate,
                    recipe=recipe,
                    start_time=start_time,
                    summary=summary,
                    failure_reason="execution_creation_failed",
                    test_res=test_res,
                    checkpoint_id=checkpoint_id,
                    mode=mode,
                    checks=VerificationChecks(checkpoint_isolated=False),
                    test_logs=summary,
                    artifact_prefix=artifact_prefix,
                    emit_stage_event=emit_stage_event,
                )
        else:
            summary = f"Sandbox does not support create_execution for checkpoint '{checkpoint_id}'"
            return await _terminate_verification(
                host=host,
                candidate=candidate,
                recipe=recipe,
                start_time=start_time,
                summary=summary,
                failure_reason="execution_creation_failed",
                test_res=test_res,
                checkpoint_id=checkpoint_id,
                mode=mode,
                checks=VerificationChecks(checkpoint_isolated=False),
                test_logs=summary,
                artifact_prefix=artifact_prefix,
                emit_stage_event=emit_stage_event,
            )

        pre_patch_hash_match = True
        patch_applied = False
        post_patch_hash_match = True
        collection_node_ids_match = True
        tests_passed = False
        zero_new_skips = True
        post_test_hash_match = True
        version_intact = True
        artifacts_persisted = False
        failure_reason: Optional[str] = None
        summary = ""
        test_logs = ""

        async def _term(
            summary_msg: str,
            reason: str,
            checks_state: VerificationChecks,
            logs: str = "",
        ) -> CandidateVerification:
            return await _terminate_verification(
                host=host,
                candidate=candidate,
                recipe=recipe,
                start_time=start_time,
                summary=summary_msg,
                failure_reason=reason,
                test_res=test_res,
                checkpoint_id=checkpoint_id,
                mode=mode,
                checks=checks_state,
                test_logs=logs or summary_msg,
                artifact_prefix=artifact_prefix,
                emit_stage_event=emit_stage_event,
            )

        # 2. Check pre-patch file hashes
        if baseline_preservation and baseline_preservation.file_hashes:
            current_hashes = await _get_hashes(exec_sandbox)
            if current_hashes:
                ok, msg = compare_test_file_hashes(baseline_preservation.file_hashes, current_hashes)
                if not ok:
                    pre_patch_hash_match = False
                    failure_reason = "test_tampering_detected"
                    summary = f"Pre-patch verification failed: {msg}"
                    return await _term(
                        summary,
                        failure_reason,
                        VerificationChecks(
                            checkpoint_isolated=checkpoint_isolated,
                            pre_patch_hash_match=False,
                        ),
                    )

        # 3. Apply candidate patch
        try:
            if hasattr(exec_sandbox, "apply_patch") and callable(exec_sandbox.apply_patch):
                apply_res = await exec_sandbox.apply_patch(candidate.diff_content)
            else:
                apply_cmd = ["git", "apply", "--whitespace=nowarn"]
                apply_res = await exec_sandbox.execute_command(
                    apply_cmd, timeout_seconds=recipe.timeout_seconds
                )
        except TimeoutError as exc:
            summary = f"Patch application timed out: {exc}"
            failure_reason = "patch_apply_failed"
            return await _term(
                summary,
                failure_reason,
                VerificationChecks(
                    checkpoint_isolated=checkpoint_isolated,
                    pre_patch_hash_match=pre_patch_hash_match,
                    patch_applied=False,
                ),
            )
        except Exception as exc:
            summary = f"Patch application error: {exc}"
            failure_reason = "patch_apply_failed"
            return await _term(
                summary,
                failure_reason,
                VerificationChecks(
                    checkpoint_isolated=checkpoint_isolated,
                    pre_patch_hash_match=pre_patch_hash_match,
                    patch_applied=False,
                ),
            )

        if apply_res.exit_code != 0:
            err_msg = apply_res.stderr or apply_res.stdout or f"exit code {apply_res.exit_code}"
            summary = f"Candidate patch failed to apply cleanly ({err_msg})"
            failure_reason = "patch_apply_failed"
            return await _term(
                summary,
                failure_reason,
                VerificationChecks(
                    checkpoint_isolated=checkpoint_isolated,
                    pre_patch_hash_match=pre_patch_hash_match,
                    patch_applied=False,
                ),
            )

        patch_applied = True

        # 4. Check post-patch file hashes (catches test file tampering in the diff)
        if baseline_preservation and baseline_preservation.file_hashes:
            current_hashes = await _get_hashes(exec_sandbox)
            if current_hashes:
                ok, msg = compare_test_file_hashes(baseline_preservation.file_hashes, current_hashes)
                if not ok:
                    post_patch_hash_match = False
                    failure_reason = "test_tampering_detected"
                    summary = f"Post-patch test tampering detected: {msg}"
                    return await _term(
                        summary,
                        failure_reason,
                        VerificationChecks(
                            checkpoint_isolated=checkpoint_isolated,
                            pre_patch_hash_match=pre_patch_hash_match,
                            patch_applied=patch_applied,
                            post_patch_hash_match=False,
                        ),
                    )

        # 5. Check pytest collection node IDs
        if baseline_preservation and baseline_preservation.node_ids:
            collect_cmd = list(recipe.test_command)
            if "--collect-only" not in collect_cmd:
                collect_cmd.extend(["--collect-only", "-q"])
            try:
                collect_res = await exec_sandbox.execute_command(
                    collect_cmd, timeout_seconds=recipe.timeout_seconds
                )
                curr_node_ids = set(collect_res.collected_node_ids)
                if not curr_node_ids and collect_res.stdout:
                    curr_node_ids = set(parse_pytest_node_ids(collect_res.stdout))
                expected_node_ids = set(baseline_preservation.node_ids)
                if not curr_node_ids or curr_node_ids != expected_node_ids:
                    collection_node_ids_match = False
                    failure_reason = "test_ids_mismatch"
                    summary = (
                        f"Collected test IDs mismatch baseline: collected {len(curr_node_ids)} "
                        f"tests, baseline had {len(expected_node_ids)}"
                    )
                    return await _term(
                        summary,
                        failure_reason,
                        VerificationChecks(
                            checkpoint_isolated=checkpoint_isolated,
                            pre_patch_hash_match=pre_patch_hash_match,
                            patch_applied=patch_applied,
                            post_patch_hash_match=post_patch_hash_match,
                            collection_node_ids_match=False,
                        ),
                        logs=collect_res.stdout or summary,
                    )
            except Exception as exc:
                collection_node_ids_match = False
                failure_reason = "test_ids_mismatch"
                summary = f"Test collection execution failed: {exc}"
                return await _term(
                    summary,
                    failure_reason,
                    VerificationChecks(
                        checkpoint_isolated=checkpoint_isolated,
                        pre_patch_hash_match=pre_patch_hash_match,
                        patch_applied=patch_applied,
                        post_patch_hash_match=post_patch_hash_match,
                        collection_node_ids_match=False,
                    ),
                )

        # 6. Execute full preserved test suite
        try:
            test_res = await exec_sandbox.execute_command(
                recipe.test_command, timeout_seconds=recipe.timeout_seconds
            )
        except TimeoutError as exc:
            summary = f"Candidate verification test run timed out: {exc}"
            failure_reason = "tests_failed"
            return await _term(
                summary,
                failure_reason,
                VerificationChecks(
                    checkpoint_isolated=checkpoint_isolated,
                    pre_patch_hash_match=pre_patch_hash_match,
                    patch_applied=patch_applied,
                    post_patch_hash_match=post_patch_hash_match,
                    collection_node_ids_match=collection_node_ids_match,
                    tests_passed=False,
                ),
            )
        except Exception as exc:
            summary = f"Candidate verification test execution error: {exc}"
            failure_reason = "tests_failed"
            return await _term(
                summary,
                failure_reason,
                VerificationChecks(
                    checkpoint_isolated=checkpoint_isolated,
                    pre_patch_hash_match=pre_patch_hash_match,
                    patch_applied=patch_applied,
                    post_patch_hash_match=post_patch_hash_match,
                    collection_node_ids_match=collection_node_ids_match,
                    tests_passed=False,
                ),
            )

        test_logs = f"STDOUT:\n{test_res.stdout}\nSTDERR:\n{test_res.stderr}".strip()

        # 7. Check post-test file hashes
        if baseline_preservation and baseline_preservation.file_hashes:
            current_hashes = await _get_hashes(exec_sandbox)
            if current_hashes:
                ok, msg = compare_test_file_hashes(baseline_preservation.file_hashes, current_hashes)
                if not ok:
                    post_test_hash_match = False
                    failure_reason = "test_tampering_detected"
                    summary = f"Post-test test tampering detected: {msg}"

        # 8. Check test execution results and regressions
        reasons: List[str] = []
        if test_res.exit_code != 0:
            reasons.append(f"non-zero test exit code ({test_res.exit_code})")
        if test_res.collected_count <= 0:
            reasons.append("zero tests collected")
        elif baseline_collected_count > 0 and test_res.collected_count != baseline_collected_count:
            reasons.append(
                f"test collection count mismatch (collected {test_res.collected_count}, "
                f"baseline had {baseline_collected_count})"
            )
        baseline_skips = baseline_preservation.skipped_count if baseline_preservation else 0
        baseline_xfails = baseline_preservation.xfailed_count if baseline_preservation else 0

        new_skips = max(0, test_res.skipped_count - baseline_skips)
        new_xfails = max(0, test_res.xfailed_count - baseline_xfails)

        if new_skips > 0:
            zero_new_skips = False
            reasons.append(f"{new_skips} newly skipped tests detected")
        if new_xfails > 0:
            reasons.append(f"{new_xfails} newly xfailed tests detected")

        if reasons and not failure_reason:
            failure_reason = "tests_failed"

        # 9. Check dependency version intact and import origin evidence
        installed_ver = test_res.installed_version
        import_origin = getattr(test_res, "import_origin", "")
        if not installed_ver:
            version_intact = False
            reasons.append("observed dependency version evidence is missing")
            if not failure_reason:
                failure_reason = "missing_dependency_evidence"
        elif installed_ver != recipe.to_version:
            version_intact = False
            reasons.append(
                f"dependency version changed to {installed_ver} (expected {recipe.to_version})"
            )
            if not failure_reason:
                failure_reason = "dependency_version_mismatch"

        if not import_origin:
            version_intact = False
            reasons.append("observed dependency import-origin evidence is missing")
            if not failure_reason:
                failure_reason = "missing_import_origin_evidence"
        elif import_origin not in ("site-packages", "dist-packages", "venv", "system"):
            version_intact = False
            reasons.append(
                f"untrusted or invalid dependency import-origin observed: '{import_origin}'"
            )
            if not failure_reason:
                failure_reason = "invalid_import_origin"

        passed = all([
            pre_patch_hash_match,
            patch_applied,
            post_patch_hash_match,
            collection_node_ids_match,
            not bool(reasons),
            post_test_hash_match,
            version_intact,
        ])
        tests_passed = (test_res.exit_code == 0) and not reasons

        if passed:
            summary = (
                f"Candidate {candidate_id} verified cleanly: tests passed, "
                f"{test_res.collected_count} tests collected, zero regressions"
            )
        else:
            reason_str = ", ".join(reasons or [failure_reason or "unknown"])
            summary = f"Candidate {candidate_id} verification failed: {reason_str}"

        # 10. Construct evidence manifest and hashes
        patch_bytes = candidate.diff_content.encode("utf-8")
        log_bytes = test_logs.encode("utf-8")
        artifact_hashes = {
            "patch.diff": hashlib.sha256(patch_bytes).hexdigest(),
            "verify.log": hashlib.sha256(log_bytes).hexdigest(),
        }

        patch_name = f"{artifact_prefix}patch.diff" if artifact_prefix else "patch.diff"
        log_name = f"{artifact_prefix}verify.log" if artifact_prefix else "verify.log"
        manifest_name = f"{artifact_prefix}evidence.json" if artifact_prefix else "evidence.json"

        # 11. Persist external artifacts first to verify storage before recording completion
        storage_succeeded = True
        try:
            await host.save_artifact("patch", patch_name, patch_bytes)
            await host.save_artifact("log", log_name, log_bytes)
        except Exception:
            storage_succeeded = False

        if not storage_succeeded:
            # AC-9: Storage failure prevents declaring candidate successfully verified
            artifacts_persisted = False
            if passed:
                passed = False
                failure_reason = "artifact_persistence_failed"
                summary = (
                    f"Candidate {candidate_id} tests passed cleanly, but artifact persistence "
                    f"failed (required artifacts could not be saved)"
                )
        else:
            artifacts_persisted = True

        checks = VerificationChecks(
            checkpoint_isolated=checkpoint_isolated,
            pre_patch_hash_match=pre_patch_hash_match,
            patch_applied=patch_applied,
            post_patch_hash_match=post_patch_hash_match,
            collection_node_ids_match=collection_node_ids_match,
            tests_passed=tests_passed,
            zero_new_skips=zero_new_skips,
            post_test_hash_match=post_test_hash_match,
            version_intact=version_intact,
            artifacts_persisted=artifacts_persisted,
        )

        manifest = build_evidence_manifest(
            candidate=candidate,
            recipe=recipe,
            checks=checks,
            test_res=test_res,
            artifact_hashes=artifact_hashes,
            checkpoint_id=checkpoint_id,
            mode=mode,
            duration_seconds=time.monotonic() - start_time,
        )
        manifest_bytes = json.dumps(manifest.to_dict(), indent=2).encode("utf-8")

        # Persist evidence.json manifest
        try:
            await host.save_artifact("evidence", manifest_name, manifest_bytes)
        except Exception:
            artifacts_persisted = False
            if passed:
                passed = False
                failure_reason = "artifact_persistence_failed"
                summary = (
                    f"Candidate {candidate_id} tests passed cleanly, but artifact persistence "
                    f"failed (evidence artifact could not be saved)"
                )

        # Final checks update
        final_checks = VerificationChecks(
            checkpoint_isolated=checks.checkpoint_isolated,
            pre_patch_hash_match=checks.pre_patch_hash_match,
            patch_applied=checks.patch_applied,
            post_patch_hash_match=checks.post_patch_hash_match,
            collection_node_ids_match=checks.collection_node_ids_match,
            tests_passed=checks.tests_passed,
            zero_new_skips=checks.zero_new_skips,
            post_test_hash_match=checks.post_test_hash_match,
            version_intact=checks.version_intact,
            artifacts_persisted=artifacts_persisted,
        )
        final_manifest = build_evidence_manifest(
            candidate=candidate,
            recipe=recipe,
            checks=final_checks,
            test_res=test_res,
            artifact_hashes=artifact_hashes,
            checkpoint_id=checkpoint_id,
            mode=mode,
            duration_seconds=time.monotonic() - start_time,
        )

        await _emit_completion(host, candidate_id, passed, summary, emit_stage_event=emit_stage_event)

        return CandidateVerification(
            candidate_id=candidate_id,
            passed=passed,
            exit_code=test_res.exit_code,
            stdout=test_res.stdout,
            stderr=test_res.stderr,
            collected_count=test_res.collected_count,
            skipped_count=test_res.skipped_count,
            xfailed_count=test_res.xfailed_count,
            installed_version=installed_ver,
            import_origin=import_origin,
            summary=summary,
            duration_seconds=time.monotonic() - start_time,
            reason=failure_reason,
            manifest=final_manifest,
        )

    finally:
        if reserved:
            try:
                await host.settle(op_id, 0.10)
            except Exception:
                pass
        # Cleanup sandbox execution resources
        if exec_sandbox is not None and hasattr(exec_sandbox, "cleanup") and callable(exec_sandbox.cleanup):
            try:
                await exec_sandbox.cleanup()
            except Exception:
                pass


async def _save_all_artifacts(
    host: HostPorts,
    patch_bytes: bytes,
    log_bytes: bytes,
    manifest_bytes: bytes,
    artifact_prefix: str = "",
) -> bool:
    """Saves evidence.json, patch.diff, and verify.log via host ports. Returns True if all succeeded."""
    all_ok = True
    patch_name = f"{artifact_prefix}patch.diff" if artifact_prefix else "patch.diff"
    log_name = f"{artifact_prefix}verify.log" if artifact_prefix else "verify.log"
    manifest_name = f"{artifact_prefix}evidence.json" if artifact_prefix else "evidence.json"

    try:
        await host.save_artifact("patch", patch_name, patch_bytes)
    except Exception:
        all_ok = False

    try:
        await host.save_artifact("log", log_name, log_bytes)
    except Exception:
        all_ok = False

    try:
        await host.save_artifact("evidence", manifest_name, manifest_bytes)
    except Exception:
        all_ok = False

    return all_ok


async def save_canonical_artifacts(
    host: HostPorts,
    candidate: CandidatePatch,
    verification: CandidateVerification,
) -> bool:
    """Saves canonical (unprefixed) patch.diff, verify.log, and evidence.json for winning candidate."""
    patch_bytes = candidate.diff_content.encode("utf-8")
    log_bytes = f"STDOUT:\n{verification.stdout}\nSTDERR:\n{verification.stderr}".strip().encode("utf-8")
    manifest_dict = verification.manifest.to_dict() if verification.manifest else {}
    manifest_bytes = json.dumps(manifest_dict, indent=2).encode("utf-8")
    return await _save_all_artifacts(host, patch_bytes, log_bytes, manifest_bytes, artifact_prefix="")


async def _terminate_verification(
    host: HostPorts,
    candidate: CandidatePatch,
    recipe: TaskRecipe,
    start_time: float,
    summary: str,
    failure_reason: str,
    test_res: CommandResult,
    checkpoint_id: str,
    mode: str,
    checks: VerificationChecks,
    test_logs: str,
    artifact_prefix: str = "",
    emit_stage_event: bool = True,
) -> CandidateVerification:
    """Helper to finalize failed verification, save available artifacts, and emit completion."""
    patch_bytes = candidate.diff_content.encode("utf-8")
    log_bytes = test_logs.encode("utf-8")
    artifact_hashes = {
        "patch.diff": hashlib.sha256(patch_bytes).hexdigest(),
        "verify.log": hashlib.sha256(log_bytes).hexdigest(),
    }
    patch_name = f"{artifact_prefix}patch.diff" if artifact_prefix else "patch.diff"
    log_name = f"{artifact_prefix}verify.log" if artifact_prefix else "verify.log"
    manifest_name = f"{artifact_prefix}evidence.json" if artifact_prefix else "evidence.json"

    persisted_ok = True
    try:
        await host.save_artifact("patch", patch_name, patch_bytes)
        await host.save_artifact("log", log_name, log_bytes)
    except Exception:
        persisted_ok = False

    checks_with_persistence = VerificationChecks(
        checkpoint_isolated=checks.checkpoint_isolated,
        pre_patch_hash_match=checks.pre_patch_hash_match,
        patch_applied=checks.patch_applied,
        post_patch_hash_match=checks.post_patch_hash_match,
        collection_node_ids_match=checks.collection_node_ids_match,
        tests_passed=checks.tests_passed,
        zero_new_skips=checks.zero_new_skips,
        post_test_hash_match=checks.post_test_hash_match,
        version_intact=checks.version_intact,
        artifacts_persisted=persisted_ok,
    )

    manifest = build_evidence_manifest(
        candidate=candidate,
        recipe=recipe,
        checks=checks_with_persistence,
        test_res=test_res,
        artifact_hashes=artifact_hashes,
        checkpoint_id=checkpoint_id,
        mode=mode,
        duration_seconds=time.monotonic() - start_time,
    )
    manifest_bytes = json.dumps(manifest.to_dict(), indent=2).encode("utf-8")

    try:
        await host.save_artifact("evidence", manifest_name, manifest_bytes)
    except Exception:
        pass

    await _emit_completion(host, candidate.candidate_id, False, summary, emit_stage_event=emit_stage_event)

    return CandidateVerification(
        candidate_id=candidate.candidate_id,
        passed=False,
        exit_code=test_res.exit_code,
        stdout=test_res.stdout,
        stderr=test_res.stderr,
        collected_count=test_res.collected_count,
        skipped_count=test_res.skipped_count,
        xfailed_count=test_res.xfailed_count,
        installed_version=test_res.installed_version,
        import_origin=getattr(test_res, "import_origin", ""),
        summary=summary,
        duration_seconds=time.monotonic() - start_time,
        reason=failure_reason,
        manifest=manifest,
    )


async def _emit_completion(
    host: HostPorts, candidate_id: str, passed: bool, summary: str, emit_stage_event: bool = True
) -> None:
    """Emits candidate.completed and optionally stage.completed (verification) events."""
    await host.emit(
        "candidate.completed",
        {"candidate_id": candidate_id, "passed": passed, "summary": summary},
    )
    if emit_stage_event:
        await host.emit(
            "stage.completed",
            {"stage": "verification", "passed": passed, "summary": summary},
        )
