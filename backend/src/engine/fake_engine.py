from src.contracts import RepairRequest, TaskRecipe, HostPorts, RepairResult


async def repair(request: RepairRequest, recipe: TaskRecipe, host: HostPorts) -> RepairResult:
    # 1. Baseline stage
    await host.emit("stage.completed", {
        "stage": "baseline",
        "passed": True,
        "summary": "Baseline tests passed cleanly",
    })

    # 2. Reserve budget
    reserved = await host.reserve("model:1", 0.05)
    if not reserved:
        return RepairResult(state="failed", reason="Budget denied")

    # 3. Check cancellation
    if await host.cancelled():
        return RepairResult(state="cancelled", reason="User cancelled")

    # 4. Upgrade stage
    await host.emit("stage.completed", {
        "stage": "upgrade",
        "passed": True,
        "summary": "Dependency upgrade reproduced failure",
    })

    # 5. Settle budget and emit usage update
    await host.settle("model:1", 0.05)
    await host.emit("usage.updated", {
        "model_calls": 1,
        "input_tokens": 120,
        "output_tokens": 80,
        "estimated_usd": 0.05,
    })

    # 6. Candidate completed
    await host.emit("candidate.completed", {
        "candidate_id": "candidate-1",
        "passed": True,
        "summary": "Candidate patch verified",
    })

    # 7. Verification stage completed
    await host.emit("stage.completed", {
        "stage": "verification",
        "passed": True,
        "summary": "Verified candidate in fresh environment",
    })

    # Note: B remains responsible for emitting the final run.finished event
    return RepairResult(state="succeeded", reason="Fake success")
