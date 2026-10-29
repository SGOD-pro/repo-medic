import asyncio
import json
import logging
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import settings
from src.contracts import RunSummary
from src.storage.repository import D1StorageRepository
from src.worker import execute_claimed_run

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("test_jwt_live")

async def main():
    repo = D1StorageRepository()
    task_id = "TASK-DEMO-JWT"
    task = repo.get_task(task_id)
    if not task:
        logger.error(f"Task {task_id} not found in database! Syncing fixtures...")
        fixture_path = Path(__file__).resolve().parent.parent / "fixtures" / "tasks" / f"{task_id}.json"
        with open(fixture_path) as f:
            repo.upsert_task(json.load(f))
        task = repo.get_task(task_id)

    print(f"Task found: {task.task_id} - {task.title}")
    print(f"Repository: {task.repository_url} @ {task.commit_sha}")
    print(f"Dependency: {task.dependency} {task.from_version} -> {task.to_version}")

    # Check budget
    committed = repo.get_total_committed_usd()
    max_run = getattr(settings, "repomedic_max_run_usd", 2.0)
    total_budget = getattr(settings, "repomedic_total_budget_usd", 25.0)
    print(f"Committed: ${committed:.2f} USD, Max Run: ${max_run:.2f} USD, Total Budget: ${total_budget:.2f} USD")
    if (committed + max_run) > total_budget:
        print("ERROR: Insufficient budget remaining!")
        sys.exit(1)

    # Create run
    import uuid
    run_id = f"run_{uuid.uuid4().hex}"
    print(f"Creating live sequential run: {run_id}")
    run = repo.create_run(
        run_id=run_id,
        task_id=task_id,
        mode="live",
        search_mode="sequential",
        max_run_usd=max_run,
    )
    print(f"Run created in state: {run.state}")

    # Execute with real providers
    print(f"Executing run {run_id} using ConTree Sandbox and TokenFactory Model...")
    success = await execute_claimed_run(run_id=run_id, repo=repo)
    print(f"Worker execution returned: {success}")

    # Fetch finished run
    finished_run = repo.get_run(run_id)
    print("\n=== FINISHED RUN SUMMARY ===")
    print(f"Run ID: {finished_run.run_id}")
    print(f"State: {finished_run.state}")
    print(f"Reason: {finished_run.reason}")
    print(f"Usage: {finished_run.usage}")
    print(f"Artifacts: {len(finished_run.artifacts)}")
    for a in finished_run.artifacts:
        print(f"  - {a.kind}: {a.filename} ({a.artifact_id})")

    # Fetch evidence if available
    for a in finished_run.artifacts:
        if a.kind == "evidence":
            evidence_bytes = repo.get_artifact_content(run_id, a.artifact_id)
            print("\n=== EVIDENCE.JSON ===")
            print(evidence_bytes.decode()[:1500])
        elif a.kind == "patch":
            patch_bytes = repo.get_artifact_content(run_id, a.artifact_id)
            print("\n=== PATCH.DIFF ===")
            print(patch_bytes.decode()[:1500])

if __name__ == "__main__":
    asyncio.run(main())

