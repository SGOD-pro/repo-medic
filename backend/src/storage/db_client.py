import os
from typing import Any, Dict, List, Optional
import httpx
from src.config import settings


class RepoMedicDB:
    """Python client for the Cloudflare D1 database bridge API."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 10.0,
        transport: Optional[httpx.BaseTransport] = None,
    ):
        self.base_url = (base_url or settings.repomedic_db_worker_url).rstrip("/")
        self.api_key = api_key or settings.db_bridge_token or settings.repomedic_db_worker_token
        self.timeout = timeout
        self.transport = transport

    def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))

        with httpx.Client(timeout=self.timeout, transport=self.transport) as client:
            response = client.request(
                method,
                f"{self.base_url}{path}",
                headers=headers,
                **kwargs,
            )
            response.raise_for_status()
            return response.json()

    def health(self) -> Dict[str, Any]:
        """Check Worker bridge availability.

        Health is an unauthenticated liveness probe by design, matching the worker bridge configuration.
        """
        with httpx.Client(timeout=self.timeout, transport=self.transport) as client:
            response = client.get(f"{self.base_url}/health")
            response.raise_for_status()
            return response.json()

    # --- Runs ---

    def create_run(
        self,
        run_id: str,
        task_id: str,
        mode: str,
        search_mode: str,
        max_run_usd: float = 2.0,
        state: str = "queued",
        created_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Insert a queued run into D1."""
        payload: Dict[str, Any] = {
            "run_id": run_id,
            "task_id": task_id,
            "mode": mode,
            "search_mode": search_mode,
            "state": state,
            "max_run_micro_usd": int(max_run_usd * 1_000_000),
        }
        if created_at is not None:
            payload["created_at"] = created_at
        return self._request(
            "POST",
            "/api/runs",
            json=payload,
        )

    def get_run(self, run_id: str) -> Dict[str, Any]:
        """Retrieve run details and artifact summary from D1."""
        return self._request("GET", f"/api/runs/{run_id}")

    def update_run_state(
        self,
        run_id: str,
        state: str,
        reason: Optional[str] = None,
        from_state: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update run state (e.g. running, succeeded, failed, cancelled)."""
        payload: Dict[str, Any] = {"state": state, "reason": reason}
        if from_state is not None:
            payload["from_state"] = from_state
        return self._request(
            "PATCH",
            f"/api/runs/{run_id}",
            json=payload,
        )

    # --- Events ---

    def create_event(
        self,
        run_id: str,
        event_type: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Append an event to a run, atomically assigning sequence ID."""
        return self._request(
            "POST",
            f"/api/runs/{run_id}/events",
            json={
                "type": event_type,
                "payload": payload,
            },
        )

    def list_events(
        self,
        run_id: str,
        after: int = 0,
    ) -> List[Dict[str, Any]]:
        """List events for a run ordered by sequence ID with optional cursor."""
        # Intentionally omit after param when after == 0 because Worker defaults after to 0
        params = {"after": after} if after > 0 else {}
        result = self._request("GET", f"/api/runs/{run_id}/events", params=params)
        return result.get("events", [])

    # --- Artifacts ---

    def store_artifact(
        self,
        run_id: str,
        artifact_id: str,
        kind: str,
        filename: str,
        sha256: str,
        size_bytes: int,
        content_base64: str,
    ) -> Dict[str, Any]:
        """Store an artifact payload in D1 within bounded size limits."""
        return self._request(
            "POST",
            f"/api/runs/{run_id}/artifacts",
            json={
                "artifact_id": artifact_id,
                "kind": kind,
                "filename": filename,
                "sha256": sha256,
                "size_bytes": size_bytes,
                "content_base64": content_base64,
            },
        )

    def get_artifact(
        self,
        run_id: str,
        artifact_id: str,
    ) -> Dict[str, Any]:
        """Fetch stored artifact metadata and content."""
        return self._request("GET", f"/api/runs/{run_id}/artifacts/{artifact_id}")

    # --- Budgets / Operations ---

    def reserve_budget(
        self,
        run_id: str,
        operation_id: str,
        kind: str,
        estimated_usd: float,
    ) -> Dict[str, Any]:
        """Reserve budget for an operation with atomic capacity check."""
        return self._request(
            "POST",
            f"/api/runs/{run_id}/operations",
            json={
                "operation_id": operation_id,
                "kind": kind,
                "reserved_micro_usd": int(estimated_usd * 1_000_000),
            },
        )

    def settle_budget(
        self,
        operation_id: str,
        actual_usd: float,
    ) -> Dict[str, Any]:
        """Settle an operation with actual cost."""
        return self._request(
            "PATCH",
            f"/api/operations/{operation_id}",
            json={"settled_micro_usd": int(actual_usd * 1_000_000)},
        )

    def record_provider_ref(
        self,
        operation_id: str,
        provider_ref: str,
    ) -> Dict[str, Any]:
        """Record external provider reference for an operation."""
        return self._request(
            "PATCH",
            f"/api/operations/{operation_id}/provider_ref",
            json={"provider_ref": provider_ref},
        )

    def list_runs(
        self,
        limit: int = 50,
        task_id: Optional[str] = None,
        state: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List runs with optional limit, task_id, and state filters."""
        params: Dict[str, Any] = {"limit": limit}
        if task_id:
            params["task_id"] = task_id
        if state:
            params["state"] = state
        result = self._request("GET", "/api/runs", params=params)
        return result.get("runs", [])

    # --- Tasks ---

    def list_tasks(self) -> List[Dict[str, Any]]:
        """List all tasks registered in D1."""
        result = self._request("GET", "/api/tasks")
        return result.get("tasks", [])

    def get_task(self, task_id: str) -> Dict[str, Any]:
        """Fetch task details by task ID from D1."""
        return self._request("GET", f"/api/tasks/{task_id}")

    def upsert_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Upsert a task into D1."""
        return self._request("POST", "/api/tasks", json=task_data)
