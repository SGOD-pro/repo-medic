from backend.src.contracts import RepairRequest, TaskRecipe, HostPorts, RepairResult

async def repair(request: RepairRequest, recipe: TaskRecipe, host: HostPorts) -> RepairResult:
    await host.emit("status", {"message": "Starting fake repair"})
    await host.reserve("model:1", 0.05)
    if await host.cancelled():
        return RepairResult(state="cancelled", reason="User cancelled")
    await host.settle("model:1", 0.05)
    return RepairResult(state="succeeded", reason="Fake success")
