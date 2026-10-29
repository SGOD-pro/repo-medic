import re
from typing import List
from src.contracts import HostPorts, TaskRecipe
from src.engine.adapters import SandboxAdapter
from src.engine.candidate import UpgradeResult


def derive_upgrade_command(dependency: str, to_version: str) -> List[str]:
    """Derives standard package upgrade command."""
    return ["pip", "install", f"{dependency}=={to_version}"]


async def run_upgrade_stage(
    recipe: TaskRecipe, sandbox: SandboxAdapter, host: HostPorts
) -> UpgradeResult:
    """
    Executes the dependency upgrade stage.
    1. Installs the new dependency version in the sandbox.
    2. Runs the test suite to verify that the expected failure is reproduced.
    Emits stage.completed event with stage='upgrade'.
    """
    # 1. Execute package upgrade
    upgrade_cmd = derive_upgrade_command(recipe.dependency, recipe.to_version)
    try:
        upgrade_res = await sandbox.execute_command(
            upgrade_cmd, timeout_seconds=recipe.timeout_seconds
        )
    except TimeoutError as exc:
        summary = f"Upgrade installation timed out: {exc}"
        await host.emit(
            "stage.completed", {"stage": "upgrade", "passed": False, "summary": summary}
        )
        return UpgradeResult(success=False, summary=summary)
    except Exception as exc:
        summary = f"Upgrade installation failed with error: {exc}"
        await host.emit(
            "stage.completed", {"stage": "upgrade", "passed": False, "summary": summary}
        )
        return UpgradeResult(success=False, summary=summary)

    if upgrade_res.exit_code != 0:
        err_msg = upgrade_res.stderr or upgrade_res.stdout or f"exit code {upgrade_res.exit_code}"
        summary = f"Package upgrade command failed ({err_msg})"
        await host.emit(
            "stage.completed", {"stage": "upgrade", "passed": False, "summary": summary}
        )
        return UpgradeResult(success=False, summary=summary, exit_code=upgrade_res.exit_code)

    installed_ver = upgrade_res.installed_version
    if not installed_ver:
        summary = "Package upgrade failed: missing observed dependency version evidence"
        await host.emit(
            "stage.completed", {"stage": "upgrade", "passed": False, "summary": summary}
        )
        return UpgradeResult(success=False, summary=summary, exit_code=1)
    if installed_ver != recipe.to_version:
        summary = (
            f"Package upgrade installed version '{installed_ver}' does not match requested '{recipe.to_version}'"
        )
        await host.emit(
            "stage.completed", {"stage": "upgrade", "passed": False, "summary": summary}
        )
        return UpgradeResult(
            success=False, installed_version=installed_ver, summary=summary, exit_code=1
        )

    # 2. Run test suite to reproduce expected failure
    try:
        test_res = await sandbox.execute_command(
            recipe.test_command, timeout_seconds=recipe.timeout_seconds
        )
    except TimeoutError as exc:
        summary = f"Post-upgrade test execution timed out: {exc}"
        await host.emit(
            "stage.completed", {"stage": "upgrade", "passed": False, "summary": summary}
        )
        return UpgradeResult(
            success=False, installed_version=installed_ver, summary=summary
        )
    except Exception as exc:
        summary = f"Post-upgrade test execution error: {exc}"
        await host.emit(
            "stage.completed", {"stage": "upgrade", "passed": False, "summary": summary}
        )
        return UpgradeResult(
            success=False, installed_version=installed_ver, summary=summary
        )

    combined_output = f"{test_res.stdout}\n{test_res.stderr}".strip()

    has_expected = bool(recipe.expected_failure and recipe.expected_failure.strip())

    if has_expected:
        expected = recipe.expected_failure.strip()
        # If tests unexpectedly pass, upgrade failure was NOT reproduced
        if test_res.exit_code == 0:
            summary = (
                f"Upgrade to {recipe.to_version} installed, but tests passed cleanly without reproducing "
                f"expected failure '{expected}'"
            )
            await host.emit(
                "stage.completed", {"stage": "upgrade", "passed": False, "summary": summary}
            )
            return UpgradeResult(
                success=False,
                installed_version=installed_ver,
                failure_output=combined_output,
                exit_code=0,
                failure_reproduced=False,
                summary=summary,
            )

        # Check whether the expected failure string or pattern is present
        failure_matched = expected in combined_output or bool(
            re.search(re.escape(expected), combined_output, re.IGNORECASE)
        )

        if not failure_matched:
            summary = (
                f"Post-upgrade tests failed with exit code {test_res.exit_code}, but expected failure "
                f"pattern '{expected}' was not observed"
            )
            await host.emit(
                "stage.completed", {"stage": "upgrade", "passed": False, "summary": summary}
            )
            return UpgradeResult(
                success=False,
                installed_version=installed_ver,
                failure_output=combined_output,
                exit_code=test_res.exit_code,
                failure_reproduced=False,
                summary=summary,
            )
    else:
        # Automatic regression discovery: no expected failure string provided
        if test_res.exit_code == 0:
            summary = f"Upgrade to {recipe.to_version} installed cleanly. No regression detected in test suite."
            await host.emit(
                "stage.completed", {"stage": "upgrade", "passed": True, "summary": summary}
            )
            return UpgradeResult(
                success=True,
                installed_version=installed_ver,
                failure_output=combined_output,
                exit_code=0,
                failure_reproduced=False,
                summary=summary,
                no_regression_detected=True,
            )

        # Distinguish test execution failure from environment/collection failure
        if test_res.exit_code in (2, 3, 4, 5) or ("ERROR collecting" in combined_output and "failed" not in combined_output.lower()):
            summary = f"Post-upgrade test collection failed under {recipe.to_version} (exit code {test_res.exit_code})"
            await host.emit(
                "stage.completed", {"stage": "upgrade", "passed": False, "summary": summary}
            )
            return UpgradeResult(
                success=False,
                installed_version=installed_ver,
                failure_output=combined_output,
                exit_code=test_res.exit_code,
                failure_reproduced=False,
                summary=summary,
            )

        expected = "discovered test failure"

    # Upgrade succeeded and expected/discovered failure reproduced
    checkpoint_id = "chk_upgrade"
    if hasattr(sandbox, "capture_checkpoint") and callable(sandbox.capture_checkpoint):
        try:
            captured = await sandbox.capture_checkpoint(tag=f"chk_{recipe.task_id}_upgrade")
            if captured:
                checkpoint_id = captured
        except Exception:
            pass

    if has_expected:
        summary = (
            f"Upgrade to {recipe.to_version} verified and reproduced expected failure '{expected}'"
        )
    else:
        summary = (
            f"Upgrade to {recipe.to_version} verified; captured test regression automatically (exit code {test_res.exit_code})"
        )
    await host.emit(
        "stage.completed", {"stage": "upgrade", "passed": True, "summary": summary}
    )
    return UpgradeResult(
        success=True,
        installed_version=installed_ver,
        failure_output=combined_output,
        exit_code=test_res.exit_code,
        failure_reproduced=True,
        checkpoint_id=checkpoint_id,
        summary=summary,
    )
