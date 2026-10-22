import asyncio
import json
import logging
from pathlib import Path

from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from pydantic import ValidationError

from src.config import settings
from src.contracts import HostPorts, RepairRequest, RepairResult, TaskRecipe
from src.engine import fake_engine
from src.engine.repair import repair as engine_repair
from src.fixtures import find_task_fixture_dir
from src.storage.repository import D1HostPorts, D1StorageRepository

logger = logging.getLogger("repomedic.worker")


def load_task_recipe(task_id: str, repo: D1StorageRepository) -> TaskRecipe:
    """Load TaskRecipe from D1 tasks record or fixture JSON file."""
    # 1. Try D1 task record
    raw_task = repo.get_task_raw(task_id)
    if raw_task:
        recipe_json_val = raw_task.get("recipe_json")
        if recipe_json_val:
            try:
                recipe_data = json.loads(recipe_json_val) if isinstance(recipe_json_val, str) else recipe_json_val
                if isinstance(recipe_data, dict):
                    merged = dict(raw_task)
                    merged.update(recipe_data)
                    return TaskRecipe.model_validate(merged)
            except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as e:
                logger.error("Failed to parse recipe_json for task %s: %s", task_id, e)

        # Check if recipe fields are directly present in raw_task
        if "test_command" in raw_task and "expected_failure" in raw_task:
            try:
                return TaskRecipe.model_validate(raw_task)
            except ValidationError as e:
                logger.error("Failed to validate raw task recipe for %s: %s", task_id, e)

    # 2. Try loading from fixture directory
    fixture_dir = find_task_fixture_dir()
    if fixture_dir:
        json_file = fixture_dir / f"{task_id}.json"
        if json_file.is_file():
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return TaskRecipe.model_validate(data)
            except (json.JSONDecodeError, ValidationError, OSError) as e:
                logger.warning("Failed to load recipe from fixture file %s: %s", json_file.name, e)

    # 3. Fallback: synthesize default TaskRecipe from TaskSummary
    task_summary = repo.get_task(task_id)
    title = task_summary.title if task_summary else f"Task {task_id}"
    repo_url = task_summary.repository_url if task_summary else "https://github.com/example/repo"
    commit_sha = task_summary.commit_sha if task_summary else "000000"
    dep = task_summary.dependency if task_summary else "pkg"
    from_ver = task_summary.from_version if task_summary else "1.0"
    to_ver = task_summary.to_version if task_summary else "2.0"

    return TaskRecipe(
        task_id=task_id,
        title=title,
        repository_url=repo_url,
        commit_sha=commit_sha,
        dependency=dep,
        from_version=from_ver,
        to_version=to_ver,
        test_command=["pytest", "tests/"],
        allowed_source_paths=["src/"],
        expected_failure="AssertionError",
        timeout_seconds=600,
        max_candidates=3,
        max_refinements=1,
    )


class QueueWorker:
    """Asynchronous background worker that claims and processes queued repair runs."""

    def __init__(
        self,
        repo: D1StorageRepository | None = None,
        poll_interval_seconds: float = 1.0,
        repair_fn: Callable[[RepairRequest, TaskRecipe, HostPorts], Awaitable[RepairResult]] | None = None,
        use_real_engine: bool | None = None,
        acceptance_prefix: str | None = None,
    ) -> None:
        self.repo = repo or D1StorageRepository()
        self.poll_interval_seconds = poll_interval_seconds
        self.repair_fn = repair_fn
        if use_real_engine is not None:
            self.use_real_engine = use_real_engine
        else:
            self.use_real_engine = getattr(settings, "repomedic_use_real_engine", False)
        if acceptance_prefix is not None:
            self.acceptance_prefix = acceptance_prefix
        else:
            self.acceptance_prefix = getattr(settings, "repomedic_acceptance_prefix", "")
        self._running: bool = False
        self._loop_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start the background worker polling task."""
        if self._running:
            return
        self._running = True
        self._loop_task = asyncio.create_task(self._run_loop())
        logger.info("QueueWorker started with poll interval %.1fs", self.poll_interval_seconds)

    async def stop(self) -> None:
        """Stop the background worker polling task cleanly."""
        self._running = False
        if self._loop_task:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
            self._loop_task = None
        logger.info("QueueWorker stopped")

    async def process_one(self) -> bool:
        """Claim and process at most one queued run. Returns True if a run was processed."""
        if self.acceptance_prefix:
            queued_runs = self.repo.list_runs(limit=100, state="queued")
            matching_runs = [r for r in queued_runs if r.run_id.startswith(self.acceptance_prefix)]
            if not matching_runs:
                return False
            run = matching_runs[0]
        else:
            queued_runs = self.repo.list_runs(limit=1, state="queued")
            if not queued_runs:
                return False
            run = queued_runs[0]

        run_id = run.run_id
        logger.info("Claiming queued run %s for task %s", run_id, run.task_id)

        # Transition state to running with compare and swap
        try:
            self.repo.update_run_state(run_id, state="running", from_state="queued")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 409:
                logger.info("Run %s already claimed by another worker, skipping", run_id)
                return False
            logger.warning("Failed to claim run %s: %s", run_id, e)
            return False
        except Exception as e:
            logger.warning("Failed to claim run %s: %s", run_id, e)
            return False

        try:
            max_run_usd = settings.repomedic_max_run_usd
            run_budget = getattr(run, "max_run_micro_usd", None)
            # Per-run budget overrides the global default when set on the run record.
            if run_budget is not None and run_budget > 0:
                max_run_usd = run_budget / 1_000_000.0

            request = RepairRequest(
                run_id=run_id,
                task_id=run.task_id,
                mode=run.mode,
                search_mode=run.search_mode,
                max_run_usd=max_run_usd,
            )
            recipe = load_task_recipe(run.task_id, self.repo)
            host = D1HostPorts(run_id=run_id, repo=self.repo)

            if self.repair_fn is not None:
                repair_callable = self.repair_fn
            elif self.use_real_engine:
                repair_callable = engine_repair
            else:
                repair_callable = fake_engine.repair

            result = await repair_callable(request, recipe, host)
        except Exception as e:
            logger.exception("Run %s failed with exception: %s", run_id, e)
            error_reason = f"Unhandled error: {repr(e)}"
            try:
                self.repo.finish_run(run_id, state="failed", reason=error_reason)
            except httpx.HTTPStatusError as status_err:
                # If run was already transitioned to terminal state (e.g. cancelled), 409 is expected
                if status_err.response.status_code == 409:
                    logger.info("Run %s already in terminal state; skipping failed update", run_id)
                else:
                    raise
            return True

        logger.info("Run %s completed with state %s: %s", run_id, result.state, result.reason)
        # Attempt to transition run to terminal state and emit run.finished event.
        # This call is deliberately outside the except Exception block above, so a
        # programming error inside finish_run (e.g. AttributeError in append_event)
        # propagates directly to _run_loop rather than triggering a second
        # finish_run('failed') call that would hit the terminal state guard (409).
        # Network/HTTP errors from update_run_state are re-raised; a 409 here means
        # the run was concurrently moved to a terminal state (e.g. cancelled) and is
        # safely ignored.
        try:
            self.repo.finish_run(run_id, state=result.state, reason=result.reason)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 409:
                logger.info("Run %s already in terminal state; skipping terminal update", run_id)
            else:
                raise

        return True

    async def _run_loop(self) -> None:
        """Main polling loop."""
        while self._running:
            try:
                processed = await self.process_one()
                if not processed:
                    await asyncio.sleep(self.poll_interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                # Log any unexpected error and retry after interval to preserve worker liveness
                logger.warning("Error in QueueWorker polling cycle: %s", e)
                await asyncio.sleep(self.poll_interval_seconds)


async def run_standalone(
    repo: D1StorageRepository | None = None,
    max_runs: int | None = None,
    repair_fn: Callable[[RepairRequest, TaskRecipe, HostPorts], Awaitable[RepairResult]] | None = None,
    use_real_engine: bool | None = None,
    acceptance_prefix: str | None = None,
) -> None:
    """Run worker in standalone mode until stopped or max_runs is reached.

    Pass max_runs=0 to exit immediately without processing any runs.
    """
    poll_interval = settings.repomedic_worker_poll_interval_seconds
    worker = QueueWorker(
        repo=repo,
        poll_interval_seconds=poll_interval,
        repair_fn=repair_fn,
        use_real_engine=use_real_engine,
        acceptance_prefix=acceptance_prefix,
    )
    runs_processed = 0

    try:
        while max_runs is None or runs_processed < max_runs:
            processed = await worker.process_one()
            if processed:
                runs_processed += 1
            else:
                await asyncio.sleep(poll_interval)
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_standalone())
