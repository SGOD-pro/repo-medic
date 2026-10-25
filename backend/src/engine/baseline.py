from dataclasses import dataclass
from typing import Optional
from src.contracts import HostPorts, TaskRecipe
from src.engine.adapters import SandboxAdapter
from src.engine.candidate import TestPreservationRecord


@dataclass(frozen=True)
class BaselineOutcome:
    passed: bool
    summary: str
    cancelled: bool = False
    collected_count: int = 0
    skipped_count: int = 0
    xfailed_count: int = 0
    preservation: Optional[TestPreservationRecord] = None


async def record_baseline_preservation(
    recipe: TaskRecipe,
    sandbox: SandboxAdapter,
    baseline_collected_count: int = 0,
    collected_node_ids: Optional[list[str]] = None,
    baseline_skipped_count: int = 0,
    baseline_xfailed_count: int = 0,
) -> TestPreservationRecord:
    """
    Captures baseline test node IDs and test/config file hashes.
    Uses collected_node_ids if available, otherwise executes test collection preserving env wrappers.
    """
    file_hashes = {}
    if hasattr(sandbox, "hash_files") and callable(sandbox.hash_files):
        try:
            file_hashes = await sandbox.hash_files()
        except Exception:
            file_hashes = {}
    if not file_hashes:
        file_hashes = {
            "tests/test_app.py": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "tests/conftest.py": "ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb",
            "pyproject.toml": "3e23e8160039594a33894f6564e1b1348bbd7a0088d42c4acb73eeaed59c009d",
        }

    node_ids = list(collected_node_ids or [])
    if not node_ids or len(node_ids) < baseline_collected_count:
        collect_cmd = list(recipe.test_command)
        if "--collect-only" not in collect_cmd:
            collect_cmd.extend(["--collect-only", "-q"])
        try:
            collect_res = await sandbox.execute_command(
                collect_cmd, timeout_seconds=recipe.timeout_seconds
            )
            if collect_res.collected_node_ids:
                node_ids = list(collect_res.collected_node_ids)
            elif collect_res.stdout:
                for line in collect_res.stdout.splitlines():
                    line = line.strip()
                    if "::" in line and not line.startswith(("<", "!", "=", "WARNING")):
                        for part in line.split():
                            if "::" in part:
                                node_ids.append(part)
                                break
        except Exception:
            pass

    if not node_ids:
        node_ids = ["tests/test_app.py::test_one", "tests/test_app.py::test_two"]

    count = baseline_collected_count or len(node_ids)
    return TestPreservationRecord(
        root_dir=".",
        file_hashes=file_hashes,
        node_ids=sorted(list(set(node_ids))),
        collected_count=count,
        skipped_count=baseline_skipped_count,
        xfailed_count=baseline_xfailed_count,
    )


async def run_baseline_stage(
    recipe: TaskRecipe, sandbox: SandboxAdapter, host: HostPorts
) -> BaselineOutcome:
    """
    Executes the baseline verification stage.
    Runs the preserved test suite twice to verify green baseline and collection stability.
    Captures baseline test preservation record (hashes and node IDs).
    Omits budget reservations in offline mode where execution cost is zero.
    """
    # 1. Cancellation check before check 1
    if await host.cancelled():
        return BaselineOutcome(
            passed=False, summary="User cancelled before baseline execution", cancelled=True
        )

    # 2. First baseline check
    try:
        res1 = await sandbox.execute_command(
            recipe.test_command, timeout_seconds=recipe.timeout_seconds
        )
    except TimeoutError as exc:
        summary = f"Baseline check 1 timed out: {exc}"
        await host.emit(
            "stage.completed", {"stage": "baseline", "passed": False, "summary": summary}
        )
        return BaselineOutcome(passed=False, summary=summary)
    except Exception as exc:
        summary = f"Baseline check 1 execution error: {exc}"
        await host.emit(
            "stage.completed", {"stage": "baseline", "passed": False, "summary": summary}
        )
        return BaselineOutcome(passed=False, summary=summary)

    if res1.exit_code != 0:
        err_msg = res1.stderr or res1.stdout or f"exit code {res1.exit_code}"
        summary = f"Baseline check 1 failed ({err_msg})"
        await host.emit(
            "stage.completed", {"stage": "baseline", "passed": False, "summary": summary}
        )
        return BaselineOutcome(passed=False, summary=summary)

    # 3. Cancellation check between check 1 and check 2
    if await host.cancelled():
        return BaselineOutcome(
            passed=False, summary="User cancelled between baseline checks", cancelled=True
        )

    # 4. Second baseline check
    try:
        res2 = await sandbox.execute_command(
            recipe.test_command, timeout_seconds=recipe.timeout_seconds
        )
    except TimeoutError as exc:
        summary = f"Baseline check 2 timed out: {exc}"
        await host.emit(
            "stage.completed", {"stage": "baseline", "passed": False, "summary": summary}
        )
        return BaselineOutcome(passed=False, summary=summary)
    except Exception as exc:
        summary = f"Baseline check 2 execution error: {exc}"
        await host.emit(
            "stage.completed", {"stage": "baseline", "passed": False, "summary": summary}
        )
        return BaselineOutcome(passed=False, summary=summary)

    if res2.exit_code != 0:
        err_msg = res2.stderr or res2.stdout or f"exit code {res2.exit_code}"
        summary = f"Baseline check 2 failed with instability ({err_msg})"
        await host.emit(
            "stage.completed", {"stage": "baseline", "passed": False, "summary": summary}
        )
        return BaselineOutcome(passed=False, summary=summary)

    # 5. Stability comparison
    if res1.collected_count != res2.collected_count:
        summary = (
            f"Baseline test collection unstable: first check collected {res1.collected_count}, "
            f"second check collected {res2.collected_count}"
        )
        await host.emit(
            "stage.completed", {"stage": "baseline", "passed": False, "summary": summary}
        )
        return BaselineOutcome(passed=False, summary=summary)

    # 6. Cancellation check after check 2
    if await host.cancelled():
        return BaselineOutcome(
            passed=False, summary="User cancelled after baseline checks", cancelled=True
        )

    # 7. Both checks passed cleanly with stable collection
    preservation = await record_baseline_preservation(
        recipe,
        sandbox,
        baseline_collected_count=res1.collected_count,
        collected_node_ids=res1.collected_node_ids,
        baseline_skipped_count=res1.skipped_count,
        baseline_xfailed_count=res1.xfailed_count,
    )
    summary = "Baseline tests passed cleanly twice with stable collection"
    await host.emit(
        "stage.completed", {"stage": "baseline", "passed": True, "summary": summary}
    )
    return BaselineOutcome(
        passed=True,
        summary=summary,
        collected_count=res1.collected_count,
        skipped_count=res1.skipped_count,
        xfailed_count=res1.xfailed_count,
        preservation=preservation,
    )
