import asyncio
import base64
import hashlib
import logging
import uuid
from typing import Any, cast
import httpx
from src.config import settings
from src.contracts import (
    ArtifactKind,
    ArtifactSummary,
    EventEnvelope,
    EventType,
    HostPorts,
    Mode,
    RunSummary,
    SearchMode,
    TaskSummary,
    UsageSummary,
)
from src.storage.db_client import RepoMedicDB

logger = logging.getLogger("repomedic.repository")


class D1StorageRepository:
    """Repository wrapping low level RepoMedicDB calls into domain contract objects."""

    def __init__(self, client: RepoMedicDB | None = None):
        self.client = client or RepoMedicDB()

    def get_total_committed_usd(self) -> float:
        try:
            res = self.client.get_budget_usage()
            return float(res.get("total_micro_usd", 0)) / 1_000_000.0
        except Exception:
            return 0.0

    def create_run(
        self,
        run_id: str,
        task_id: str,
        mode: str,
        search_mode: str,
        max_run_usd: float = 2.0,
        state: str = "queued",
        created_at: str | None = None,
    ) -> RunSummary:
        self.client.create_run(
            run_id=run_id,
            task_id=task_id,
            mode=mode,
            search_mode=search_mode,
            max_run_usd=max_run_usd,
            state=state,
            created_at=created_at,
        )
        return self.get_run(run_id)

    def _map_run_summary(self, data: dict[str, Any]) -> RunSummary:
        raw_usage = data.get("usage") or {}
        usage = UsageSummary(
            model_calls=raw_usage.get("model_calls", 0),
            input_tokens=raw_usage.get("input_tokens", 0),
            output_tokens=raw_usage.get("output_tokens", 0),
            estimated_usd=float(raw_usage.get("estimated_usd", 0.0)),
        )
        raw_artifacts = data.get("artifacts") or []
        artifacts = [
            ArtifactSummary(
                artifact_id=a["artifact_id"],
                kind=a["kind"],
                filename=a["filename"],
            )
            for a in raw_artifacts
        ]
        raw_mode = data.get("mode", "offline")
        if raw_mode not in ("offline", "replay", "live"):
            mode: Mode = "offline"
        else:
            mode = cast(Mode, raw_mode)

        raw_search = data.get("search_mode", "sequential")
        if raw_search in ("depth_first", "df", "branch_refine"):
            search_mode: SearchMode = "branch_refine"
        else:
            search_mode = "sequential"

        return RunSummary(
            run_id=data["run_id"],
            task_id=data["task_id"],
            mode=mode,
            search_mode=search_mode,
            state=data["state"],
            reason=data.get("reason"),
            max_run_micro_usd=data.get("max_run_micro_usd", 0),
            usage=usage,
            artifacts=artifacts,
        )

    def get_run(self, run_id: str) -> RunSummary:
        data = self.client.get_run(run_id)
        return self._map_run_summary(data)

    def list_runs(
        self,
        limit: int = 50,
        task_id: str | None = None,
        state: str | None = None,
        run_prefix: str | None = None,
    ) -> list[RunSummary]:
        raw_runs = self.client.list_runs(
            limit=limit,
            task_id=task_id,
            state=state,
            run_prefix=run_prefix,
        )
        return [self._map_run_summary(r) for r in raw_runs]

    def cleanup_manifest(self, manifest: dict[str, list[str]]) -> dict[str, Any]:
        """Delete exact entities recorded in the acceptance manifest."""
        return self.client.cleanup_manifest(manifest)

    def list_tasks(self) -> list[TaskSummary]:
        raw_tasks = self.client.list_tasks()
        return [
            TaskSummary(
                task_id=t["task_id"],
                title=t["title"],
                repository_url=t["repository_url"],
                commit_sha=t["commit_sha"],
                dependency=t["dependency"],
                from_version=t["from_version"],
                to_version=t["to_version"],
            )
            for t in raw_tasks
        ]

    def get_task(self, task_id: str) -> TaskSummary | None:
        try:
            t = self.client.get_task(task_id)
            return TaskSummary(
                task_id=t["task_id"],
                title=t["title"],
                repository_url=t["repository_url"],
                commit_sha=t["commit_sha"],
                dependency=t["dependency"],
                from_version=t["from_version"],
                to_version=t["to_version"],
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    def get_task_raw(self, task_id: str) -> dict[str, Any] | None:
        """Retrieve raw task dictionary containing recipe fields or recipe_json from D1."""
        try:
            return self.client.get_task(task_id)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    def upsert_task(self, task_data: dict[str, Any]) -> None:
        self.client.upsert_task(task_data)

    def update_run_state(
        self,
        run_id: str,
        state: str,
        reason: str | None = None,
        from_state: str | None = None,
    ) -> None:
        self.client.update_run_state(run_id, state=state, reason=reason, from_state=from_state)

    def finish_run(self, run_id: str, state: str, reason: str | None = None) -> None:
        """Transition run to terminal state first, then emit run.finished event.

        Updating state before appending the final event ensures clients polling
        runs do not observe a finished event while the run is still reported as running.

        append_event is called best-effort: if it fails after the state update
        succeeds, the error is logged but not re-raised. The run is already in
        a terminal state, so re-raising would trigger the outer exception handler
        in worker.py and attempt a second finish_run call, producing a duplicate
        run.finished event.
        """
        self.update_run_state(run_id, state=state, reason=reason)
        try:
            self.append_event(run_id, event_type="run.finished", payload={"state": state, "reason": reason})
        except (httpx.RequestError, httpx.HTTPStatusError, OSError) as e:
            logger.error(
                "Failed to append run.finished event for run %s (state already set to %s): %s",
                run_id, state, e,
            )

    def append_event(self, run_id: str, event_type: str, payload: dict[str, Any]) -> EventEnvelope:
        result = self.client.create_event(run_id, event_type=event_type, payload=payload)
        return EventEnvelope(
            run_id=run_id,
            seq=result["seq"],
            ts=result["ts"],
            # Pydantic validates the event type during EventEnvelope construction
            type=cast(EventType, event_type),
            payload=payload,
        )

    def list_events(self, run_id: str, after: int = 0) -> list[EventEnvelope]:
        raw_events = self.client.list_events(run_id, after=after)
        return [
            EventEnvelope(
                run_id=run_id,
                seq=e["seq"],
                ts=e["ts"],
                # Pydantic validates the event type during EventEnvelope construction
                type=cast(EventType, e["type"]),
                payload=e["payload"],
            )
            for e in raw_events
        ]

    def store_artifact(
        self,
        run_id: str,
        kind: str,
        filename: str,
        content: bytes,
        artifact_id: str | None = None,
    ) -> ArtifactSummary:
        art_id = artifact_id or f"art_{uuid.uuid4().hex[:12]}"
        sha256 = hashlib.sha256(content).hexdigest()
        content_b64 = base64.b64encode(content).decode("ascii")
        self.client.store_artifact(
            run_id=run_id,
            artifact_id=art_id,
            kind=kind,
            filename=filename,
            sha256=sha256,
            size_bytes=len(content),
            content_base64=content_b64,
        )
        return ArtifactSummary(artifact_id=art_id, kind=cast(ArtifactKind, kind), filename=filename)

    def get_artifact_content(self, run_id: str, artifact_id: str) -> bytes:
        data = self.client.get_artifact(run_id, artifact_id)
        return base64.b64decode(data["content_base64"].encode("ascii"))


class D1HostPorts(HostPorts):
    """HostPorts implementation backed by the Cloudflare D1 Worker bridge."""

    def __init__(
        self,
        run_id: str,
        client: RepoMedicDB | None = None,
        repo: D1StorageRepository | None = None,
    ):
        self.run_id = run_id
        if repo is not None:
            self.repo = repo
            self.client = repo.client
        else:
            self.client = client or RepoMedicDB()
            self.repo = D1StorageRepository(self.client)
        self._is_cancelled = False

    async def emit(self, event_type: str, payload: dict[str, Any]) -> None:
        await asyncio.to_thread(self.repo.append_event, self.run_id, event_type, payload)

    async def save_artifact(self, kind: str, filename: str, content: bytes) -> str:
        art = await asyncio.to_thread(self.repo.store_artifact, self.run_id, kind, filename, content)
        return art.artifact_id

    def _scoped_op_id(self, operation_id: str) -> str:
        if operation_id.startswith(f"{self.run_id}:"):
            return operation_id
        return f"{self.run_id}:{operation_id}"

    async def reserve(self, operation_id: str, estimated_usd: float) -> bool:
        scoped_id = self._scoped_op_id(operation_id)
        kind = "sandbox" if operation_id.startswith("sandbox:") else "model"
        global_budget = getattr(settings, "repomedic_total_budget_usd", 25.0)
        try:
            await asyncio.to_thread(
                self.client.reserve_budget,
                run_id=self.run_id,
                operation_id=scoped_id,
                kind=kind,
                estimated_usd=estimated_usd,
                global_budget_usd=global_budget,
            )
            return True
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 409:
                return False
            raise

    async def settle(self, operation_id: str, actual_or_estimated_usd: float) -> None:
        scoped_id = self._scoped_op_id(operation_id)
        await asyncio.to_thread(self.client.settle_budget, scoped_id, actual_or_estimated_usd)

    async def cancelled(self) -> bool:
        if self._is_cancelled:
            return True
        try:
            run_data = await asyncio.to_thread(self.client.get_run, self.run_id)
            if run_data.get("state") == "cancelled":
                self._is_cancelled = True
                return True
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return False
            raise
        return self._is_cancelled

    async def record_provider_ref(self, operation_id: str, provider_ref: str) -> None:
        await asyncio.to_thread(self.client.record_provider_ref, operation_id, provider_ref)
