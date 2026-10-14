
import os
from typing import Any

import httpx


class RepoMedicDB:
    """Python client for the Cloudflare D1 database API."""

    def __init__(
        self,
        base_url: str = "https://repo-medic-api.souvik-dev112.workers.dev",
        api_key: str | None = "sk-583163519187bf646119c1a7c3f90a6bc7c0da407a7764ea790383f3b626a63d",
        timeout: float = 10.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or os.environ["DB_BRIDGE_TOKEN"]
        self.timeout = timeout

    def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> dict:
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

    def health(self) -> dict:
        """Check Worker availability."""
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(f"{self.base_url}/health")
            response.raise_for_status()
            return response.json()

    def create_note(self, title: str, content: str) -> dict:
        """Insert a note into D1."""
        return self._request(
            "POST",
            "/api/notes",
            json={"title": title, "content": content},
        )

    def list_notes(self) -> list[dict]:
        """Retrieve the latest notes."""
        result = self._request("GET", "/api/notes")
        return result["notes"]


if __name__ == "__main__":
    db = RepoMedicDB()

    print("Health:", db.health())

    created = db.create_note(
        title="First record",
        content="Testing Cloudflare D1 from Python",
    )
    print("Created:", created)

    notes = db.list_notes()
    print("Notes:", notes)
