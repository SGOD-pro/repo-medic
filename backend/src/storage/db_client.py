import httpx
from typing import Any, Dict, List, Optional
from backend.src.config import settings

class RepoMedicDB:
    """Python client for the Cloudflare D1 database bridge API."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 10.0,
    ):
        self.base_url = (base_url or settings.repomedic_db_worker_url).rstrip("/")
        self.api_key = api_key or settings.repo_medic_api_key
        self.timeout = timeout

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

        with httpx.Client(timeout=self.timeout) as client:
            response = client.request(
                method,
                f"{self.base_url}{path}",
                headers=headers,
                **kwargs,
            )
            response.raise_for_status()
            return response.json()

    def health(self) -> Dict[str, Any]:
        """Check Worker availability."""
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(f"{self.base_url}/health")
            response.raise_for_status()
            return response.json()

    # --- Runs ---

    def create_run(self, run_id: str, task_id: str, mode: str, search_mode: str, max_run_usd: float) -> Dict[str, Any]:
        """Insert a queued run into D1."""
        return self._request(
            "POST",
            "/api/runs",
            json={
                "run_id": run_id,
                "task_id": task_id,
                "mode": mode,
                "search_mode": search_mode,
                "state": "queued",
                "max_run_micro_usd": int(max_run_usd * 1_000_000),
            },
        )

    def get_run(self, run_id: str) -> Dict[str, Any]:
        """Retrieve a specific run."""
        return self._request("GET", f"/api/runs/{run_id}")

    def update_run_state(self, run_id: str, state: str, reason: Optional[str] = None) -> Dict[str, Any]:
        """Update run state (e.g. to running, failed, succeeded, cancelled)."""
        return self._request(
            "PATCH",
            f"/api/runs/{run_id}",
            json={"state": state, "reason": reason},
        )

    # --- Events ---

    def create_event(self, run_id: str, event_type: str, payload: dict) -> Dict[str, Any]:
        """Append a new event to a run."""
        return self._request(
            "POST",
            f"/api/runs/{run_id}/events",
            json={
                "type": event_type,
                "payload": payload,
            },
        )

    def list_events(self, run_id: str) -> List[Dict[str, Any]]:
        """List all events for a run, ordered by sequence ID."""
        result = self._request("GET", f"/api/runs/{run_id}/events")
        return result.get("events", [])

    # --- Budgets / Operations ---

    def reserve_budget(self, run_id: str, operation_id: str, kind: str, estimated_usd: float) -> Dict[str, Any]:
        """Reserve a budget amount for a provider operation."""
        return self._request(
            "POST",
            f"/api/runs/{run_id}/operations",
            json={
                "operation_id": operation_id,
                "kind": kind,
                "reserved_micro_usd": int(estimated_usd * 1_000_000),
            },
        )

    def settle_budget(self, operation_id: str, actual_usd: float) -> Dict[str, Any]:
        """Settle an operation with the actual cost."""
        return self._request(
            "PATCH",
            f"/api/operations/{operation_id}",
            json={"settled_micro_usd": int(actual_usd * 1_000_000)},
        )
