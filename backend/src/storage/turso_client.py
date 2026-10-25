from contextlib import contextmanager
import datetime
import json
import logging
import os
import re
import threading
from typing import Any, Dict, Iterator, List, Optional

import libsql  # type: ignore[import-untyped]

from src.config import settings
from src.storage.exceptions import (
    StorageConflictError,
    StorageError,
    StorageLimitExceededError,
    StorageNotFoundError,
)
from src.storage.migrations import apply_migrations

logger = logging.getLogger("repomedic.storage.turso")

RUN_ID_REGEX = re.compile(r"^[a-zA-Z0-9_-]{1,128}$")


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class TursoClient:
    """Direct libSQL and Turso storage adapter implementing the RepoMedicDB client interface."""

    def __init__(
        self,
        database: Optional[str] = None,
        auth_token: Optional[str] = None,
        timeout: float = 10.0,
    ) -> None:
        raw_db = (
            database
            or os.getenv("TURSO_DATABASE_URL")
            or os.getenv("DB_URL")
            or getattr(settings, "turso_database_url", "")
            or getattr(settings, "repomedic_database_url", "")
            or getattr(settings, "db_url", "")
        )
        raw_token = (
            auth_token
            or os.getenv("TURSO_AUTH_TOKEN")
            or os.getenv("API_KEY")
            or getattr(settings, "turso_auth_token", "")
            or getattr(settings, "repomedic_database_auth_token", "")
            or getattr(settings, "api_key", "")
        )

        self.database = raw_db.strip() if raw_db else "repomedic_local.db"
        self.auth_token = raw_token.strip() if raw_token else ""
        self.timeout = timeout
        self._lock = threading.RLock()
        self._local = threading.local()
        self._shared_memory_conn: Optional[Any] = None

        logger.info("Initializing Turso/libSQL client targeting: %s", self.database)
        init_conn = self._get_connection()
        with self._lock:
            apply_migrations(init_conn)

    def _get_connection(self) -> Any:
        if self.database == ":memory:":
            with self._lock:
                if self._shared_memory_conn is None:
                    self._shared_memory_conn = self._create_connection()
                return self._shared_memory_conn

        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = self._create_connection()
            self._local.conn = conn
        return conn

    def _create_connection(self) -> Any:
        connect_kwargs: Dict[str, Any] = {
            "timeout": self.timeout,
            "_check_same_thread": False,
            "autocommit": True,
        }
        if self.auth_token:
            connect_kwargs["auth_token"] = self.auth_token

        conn = libsql.connect(self.database, **connect_kwargs)
        try:
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.execute("PRAGMA busy_timeout = 10000;")
            if not self.database.startswith(("libsql://", "https://", "http://")) and self.database != ":memory:":
                conn.execute("PRAGMA journal_mode = WAL;")
        except Exception:
            pass
        return conn

    @property
    def _conn(self) -> Any:
        return self._get_connection()

    @contextmanager
    def _op_lock(self) -> Iterator[None]:
        if self.database == ":memory:":
            with self._lock:
                yield
        else:
            yield

    def close(self) -> None:
        with self._lock:
            if self._shared_memory_conn is not None:
                try:
                    self._shared_memory_conn.close()
                except Exception:
                    pass
                self._shared_memory_conn = None
            conn = getattr(self._local, "conn", None)
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
                self._local.conn = None

    def health(self) -> Dict[str, Any]:
        with self._op_lock():
            cur = self._conn.execute("SELECT 1")
            cur.fetchone()
        return {"ok": True, "engine": "libsql", "status": "healthy"}

    # --- Tasks ---

    def list_tasks(self) -> List[Dict[str, Any]]:
        with self._op_lock():
            cur = self._conn.execute(
                "SELECT task_id, title, repository_url, commit_sha, dependency, from_version, "
                "to_version, recipe_json FROM tasks ORDER BY created_at ASC"
            )
            rows = cur.fetchall()
            tasks = []
            for r in rows:
                tasks.append({
                    "task_id": r[0],
                    "title": r[1],
                    "repository_url": r[2],
                    "commit_sha": r[3],
                    "dependency": r[4],
                    "from_version": r[5],
                    "to_version": r[6],
                    "recipe_json": r[7],
                })
            return tasks

    def get_task(self, task_id: str) -> Dict[str, Any]:
        with self._op_lock():
            cur = self._conn.execute(
                "SELECT task_id, title, repository_url, commit_sha, dependency, from_version, "
                "to_version, recipe_json FROM tasks WHERE task_id = ?",
                (task_id,),
            )
            r = cur.fetchone()
            if not r:
                raise StorageNotFoundError("not_found", f"Task '{task_id}' not found")
            return {
                "task_id": r[0],
                "title": r[1],
                "repository_url": r[2],
                "commit_sha": r[3],
                "dependency": r[4],
                "from_version": r[5],
                "to_version": r[6],
                "recipe_json": r[7],
            }

    def upsert_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        task_id = task_data.get("task_id")
        title = task_data.get("title")
        repo_url = task_data.get("repository_url")
        commit_sha = task_data.get("commit_sha")
        dependency = task_data.get("dependency")
        from_ver = task_data.get("from_version")
        to_ver = task_data.get("to_version")

        if not all([task_id, title, repo_url, commit_sha, dependency, from_ver, to_ver]):
            raise StorageError("invalid_request", "Missing required task fields", 400)

        recipe_obj = task_data.get("recipe_json")
        if not recipe_obj and "test_command" in task_data:
            recipe_obj = {
                "test_command": task_data.get("test_command"),
                "allowed_source_paths": task_data.get("allowed_source_paths", ["src/"]),
                "expected_failure": task_data.get("expected_failure", ""),
                "timeout_seconds": task_data.get("timeout_seconds", 600),
                "max_candidates": task_data.get("max_candidates", 3),
                "max_refinements": task_data.get("max_refinements", 1),
            }
        recipe_json_str = (
            recipe_obj if isinstance(recipe_obj, str) else json.dumps(recipe_obj) if recipe_obj else None
        )
        now = _now_iso()

        with self._op_lock():
            self._conn.execute(
                """INSERT INTO tasks (
                     task_id, title, repository_url, commit_sha, dependency,
                     from_version, to_version, recipe_json, created_at
                   )
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(task_id) DO UPDATE SET
                     title = excluded.title,
                     repository_url = excluded.repository_url,
                     commit_sha = excluded.commit_sha,
                     dependency = excluded.dependency,
                     from_version = excluded.from_version,
                     to_version = excluded.to_version,
                     recipe_json = excluded.recipe_json""",
                (task_id, title, repo_url, commit_sha, dependency, from_ver, to_ver, recipe_json_str, now),
            )
            self._conn.commit()

        return {"ok": True, "task_id": task_id}

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
        if not RUN_ID_REGEX.match(run_id):
            raise StorageError(
                "invalid_request",
                "Invalid run_id format: must be 1-128 characters matching [a-zA-Z0-9_-]",
                400,
            )
        if max_run_usd < 0:
            raise StorageError("invalid_request", "max_run_usd must be non-negative", 400)

        max_micro_usd = int(max_run_usd * 1_000_000)
        now = created_at or _now_iso()
        initial_usage = json.dumps({"model_calls": 0, "input_tokens": 0, "output_tokens": 0, "estimated_usd": 0})

        with self._op_lock():
            cur = self._conn.execute("SELECT 1 FROM runs WHERE run_id = ?", (run_id,))
            if cur.fetchone():
                raise StorageConflictError("run_already_exists", f"Run with ID '{run_id}' already exists")

            self._conn.execute(
                """INSERT INTO runs (
                     run_id, task_id, mode, search_mode, state, reason,
                     usage_json, created_at, updated_at, max_run_micro_usd
                   )
                   VALUES (?, ?, ?, ?, ?, NULL, ?, ?, ?, ?)""",
                (run_id, task_id, mode, search_mode, state, initial_usage, now, now, max_micro_usd),
            )
            self._conn.commit()

        return {"ok": True, "run_id": run_id}

    def get_run(self, run_id: str) -> Dict[str, Any]:
        with self._op_lock():
            cur = self._conn.execute(
                """SELECT
                     r.run_id, r.task_id, r.mode, r.search_mode, r.state, r.reason,
                     r.usage_json, r.max_run_micro_usd,
                     COALESCE((
                       SELECT SUM(CASE WHEN o.status = 'settled' THEN o.settled_micro_usd ELSE o.reserved_micro_usd END)
                       FROM operations o
                       WHERE o.run_id = r.run_id AND o.status IN ('reserved', 'settled', 'uncertain')
                     ), 0) as ops_micro,
                     COALESCE((
                       SELECT COUNT(*)
                       FROM operations o
                       WHERE o.run_id = r.run_id AND o.kind = 'model'
                         AND o.status IN ('reserved', 'settled', 'uncertain')
                     ), 0) as model_count
                   FROM runs r WHERE r.run_id = ?""",
                (run_id,),
            )
            r = cur.fetchone()
            if not r:
                raise StorageNotFoundError("not_found", f"Run '{run_id}' not found")

            artifacts_cur = self._conn.execute(
                "SELECT artifact_id, kind, filename FROM artifacts WHERE run_id = ? ORDER BY created_at ASC",
                (run_id,),
            )
            artifacts = [
                {"artifact_id": a[0], "kind": a[1], "filename": a[2]}
                for a in artifacts_cur.fetchall()
            ]

            usage = {"model_calls": 0, "input_tokens": 0, "output_tokens": 0, "estimated_usd": 0.0}
            try:
                usage.update(json.loads(r[6]))
            except Exception:
                pass

            ops_micro = r[8]
            if ops_micro > 0 or usage["estimated_usd"] == 0:
                usage["estimated_usd"] = ops_micro / 1_000_000.0

            model_count = r[9]
            if model_count > 0 and usage["model_calls"] == 0:
                usage["model_calls"] = model_count

            return {
                "run_id": r[0],
                "task_id": r[1],
                "mode": r[2],
                "search_mode": r[3],
                "state": r[4],
                "reason": r[5],
                "max_run_micro_usd": r[7],
                "usage": usage,
                "artifacts": artifacts,
            }

    def get_run_state(self, run_id: str) -> Optional[str]:
        with self._op_lock():
            cur = self._conn.execute("SELECT state FROM runs WHERE run_id = ?", (run_id,))
            row = cur.fetchone()
            return row[0] if row else None

    def update_run_state(
        self,
        run_id: str,
        state: str,
        reason: Optional[str] = None,
        from_state: Optional[str] = None,
    ) -> Dict[str, Any]:
        allowed_states = ["queued", "running", "succeeded", "failed", "cancelled"]
        if state not in allowed_states:
            raise StorageError("invalid_state", f"Invalid state '{state}'", 400)

        terminal_states = ["succeeded", "failed", "cancelled"]
        now = _now_iso()

        with self._op_lock():
            cur = self._conn.execute("SELECT state FROM runs WHERE run_id = ?", (run_id,))
            row = cur.fetchone()
            if not row:
                raise StorageNotFoundError("not_found", f"Run '{run_id}' not found")

            current_state = row[0]
            if current_state in terminal_states:
                raise StorageConflictError(
                    "terminal_state_immutable",
                    f"Cannot transition run from terminal state '{current_state}'",
                )

            if from_state and current_state != from_state:
                raise StorageConflictError(
                    "state_conflict",
                    f"Run state '{current_state}' does not match expected from_state '{from_state}'",
                )

            if from_state:
                res = self._conn.execute(
                    "UPDATE runs SET state = ?, reason = ?, updated_at = ? WHERE run_id = ? AND state = ?",
                    (state, reason, now, run_id, from_state),
                )
                if res.rowcount == 0:
                    raise StorageConflictError("state_conflict", "State conflict during transition")
            else:
                res = self._conn.execute(
                    "UPDATE runs SET state = ?, reason = ?, updated_at = ? "
                    "WHERE run_id = ? AND state NOT IN ('succeeded', 'failed', 'cancelled')",
                    (state, reason, now, run_id),
                )
                if res.rowcount == 0:
                    raise StorageConflictError(
                        "terminal_state_immutable",
                        "Run is in a terminal state and cannot be updated",
                    )

            self._conn.commit()

        return {"ok": True}

    def list_runs(
        self,
        limit: int = 50,
        task_id: Optional[str] = None,
        state: Optional[str] = None,
        run_prefix: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        limit = min(max(limit, 1), 100)
        query = (
            "SELECT r.run_id, r.task_id, r.mode, r.search_mode, r.state, r.reason, "
            "r.usage_json, r.created_at, r.max_run_micro_usd, "
            "COALESCE(( "
            "  SELECT SUM(CASE WHEN o.status = 'settled' THEN o.settled_micro_usd ELSE o.reserved_micro_usd END) "
            "  FROM operations o "
            "  WHERE o.run_id = r.run_id AND o.status IN ('reserved', 'settled', 'uncertain') "
            "), 0) as ops_micro, "
            "COALESCE(( "
            "  SELECT COUNT(*) "
            "  FROM operations o "
            "  WHERE o.run_id = r.run_id AND o.kind = 'model' "
            "    AND o.status IN ('reserved', 'settled', 'uncertain') "
            "), 0) as model_count "
            "FROM runs r"
        )
        conditions = []
        params: List[Any] = []

        if task_id:
            conditions.append("r.task_id = ?")
            params.append(task_id)
        if state:
            conditions.append("r.state = ?")
            params.append(state)
        if run_prefix:
            escaped_prefix = run_prefix.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            conditions.append("r.run_id LIKE ? ESCAPE '\\'")
            params.append(f"{escaped_prefix}%")

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        if state == "queued":
            query += " ORDER BY r.created_at ASC, r.run_id ASC LIMIT ?"
        else:
            query += " ORDER BY r.created_at DESC, r.run_id ASC LIMIT ?"
        params.append(limit)

        with self._op_lock():
            cur = self._conn.execute(query, tuple(params))
            rows = cur.fetchall()

            if not rows:
                return []

            run_ids = [r[0] for r in rows]
            artifacts_by_run: Dict[str, List[Dict[str, Any]]] = {rid: [] for rid in run_ids}

            # Batch load artifacts in 1 single query for all returned runs
            placeholders = ",".join(["?"] * len(run_ids))
            art_cur = self._conn.execute(
                ("SELECT run_id, artifact_id, kind, filename FROM artifacts "
                 f"WHERE run_id IN ({placeholders}) ORDER BY created_at ASC"),
                tuple(run_ids),
            )
            for art_row in art_cur.fetchall():
                art_run_id = art_row[0]
                if art_run_id in artifacts_by_run:
                    artifacts_by_run[art_run_id].append({
                        "artifact_id": art_row[1],
                        "kind": art_row[2],
                        "filename": art_row[3],
                    })

            runs = []
            for r in rows:
                rid = r[0]
                artifacts = artifacts_by_run.get(rid, [])

                usage = {"model_calls": 0, "input_tokens": 0, "output_tokens": 0, "estimated_usd": 0.0}
                try:
                    usage.update(json.loads(r[6]))
                except Exception:
                    pass

                ops_micro = r[9]
                if ops_micro > 0 or usage["estimated_usd"] == 0:
                    usage["estimated_usd"] = ops_micro / 1_000_000.0

                model_count = r[10]
                if model_count > 0 and usage["model_calls"] == 0:
                    usage["model_calls"] = model_count

                runs.append({
                    "run_id": rid,
                    "task_id": r[1],
                    "mode": r[2],
                    "search_mode": r[3],
                    "state": r[4],
                    "reason": r[5],
                    "max_run_micro_usd": r[8],
                    "usage": usage,
                    "artifacts": artifacts,
                })

            return runs

    # --- Events ---

    def create_event(
        self,
        run_id: str,
        event_type: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        if not event_type:
            raise StorageError("invalid_request", "Event type is required", 400)
        if not isinstance(payload, dict):
            raise StorageError("invalid_request", "Event payload must be a dictionary", 400)

        now = _now_iso()
        payload_json = json.dumps(payload)

        with self._op_lock():
            cur = self._conn.execute("SELECT 1 FROM runs WHERE run_id = ?", (run_id,))
            if not cur.fetchone():
                raise StorageNotFoundError("not_found", f"Run '{run_id}' not found")

            res = self._conn.execute(
                """INSERT INTO events (run_id, seq, ts, type, payload_json)
                   VALUES (?, (SELECT COALESCE(MAX(seq), 0) + 1 FROM events WHERE run_id = ?), ?, ?, ?)
                   RETURNING seq, ts""",
                (run_id, run_id, now, event_type, payload_json),
            )
            rows = res.fetchall()
            if not rows:
                raise StorageError("internal_error", "Failed to insert event", 500)

            seq, ts = rows[0][0], rows[0][1]

            if event_type == "usage.updated":
                self._conn.execute(
                    "UPDATE runs SET usage_json = ?, updated_at = ? WHERE run_id = ?",
                    (payload_json, now, run_id),
                )

            self._conn.commit()

        return {"ok": True, "seq": seq, "ts": ts}

    def list_events(
        self,
        run_id: str,
        after: int = 0,
    ) -> List[Dict[str, Any]]:
        with self._op_lock():
            cur = self._conn.execute(
                "SELECT seq, type, payload_json, ts FROM events WHERE run_id = ? AND seq > ? ORDER BY seq ASC",
                (run_id, after),
            )
            rows = cur.fetchall()
            if not rows and after == 0:
                check_cur = self._conn.execute("SELECT 1 FROM runs WHERE run_id = ?", (run_id,))
                if not check_cur.fetchone():
                    raise StorageNotFoundError("not_found", f"Run '{run_id}' not found")

            events = []
            for r in rows:
                try:
                    p = json.loads(r[2])
                except Exception:
                    p = r[2]
                events.append({
                    "seq": r[0],
                    "type": r[1],
                    "payload": p,
                    "ts": r[3],
                })
            return events

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
        if size_bytes > 1048576:
            raise StorageLimitExceededError(
                "artifact_size_limit_exceeded",
                "Individual artifact exceeds limit of 1048576 bytes",
            )

        now = _now_iso()

        with self._op_lock():
            res = self._conn.execute(
                """INSERT INTO artifacts (
                     artifact_id, run_id, kind, filename, sha256,
                     size_bytes, content_base64, created_at
                   )
                   SELECT ?, ?, ?, ?, ?, ?, ?, ?
                   WHERE EXISTS (SELECT 1 FROM runs WHERE run_id = ?)
                     AND (
                       SELECT COALESCE(SUM(size_bytes), 0)
                       FROM artifacts
                       WHERE run_id = ?
                     ) + ? <= 8388608""",
                (artifact_id, run_id, kind, filename, sha256, size_bytes,
                 content_base64, now, run_id, run_id, size_bytes),
            )
            if res.rowcount == 0:
                cur = self._conn.execute("SELECT 1 FROM runs WHERE run_id = ?", (run_id,))
                if not cur.fetchone():
                    raise StorageNotFoundError("not_found", f"Run '{run_id}' not found")
                raise StorageLimitExceededError(
                    "run_artifact_volume_limit_exceeded",
                    "Total run artifact volume exceeds limit of 8388608 bytes",
                )

            self._conn.commit()

        return {"ok": True, "artifact_id": artifact_id}

    def get_artifact(
        self,
        run_id: str,
        artifact_id: str,
    ) -> Dict[str, Any]:
        with self._op_lock():
            cur = self._conn.execute(
                "SELECT artifact_id, kind, filename, sha256, size_bytes, content_base64 "
                "FROM artifacts WHERE run_id = ? AND artifact_id = ?",
                (run_id, artifact_id),
            )
            r = cur.fetchone()
            if not r:
                raise StorageNotFoundError("not_found", f"Artifact '{artifact_id}' not found")
            return {
                "artifact_id": r[0],
                "kind": r[1],
                "filename": r[2],
                "sha256": r[3],
                "size_bytes": r[4],
                "content_base64": r[5],
            }

    # --- Budgets & Operations ---

    def get_budget_usage(self) -> Dict[str, Any]:
        with self._op_lock():
            cur = self._conn.execute(
                """SELECT
                     COALESCE(SUM(CASE WHEN status = 'settled' THEN settled_micro_usd ELSE 0 END), 0)
                       as settled_micro_usd,
                     COALESCE(SUM(CASE WHEN status = 'reserved' THEN reserved_micro_usd ELSE 0 END), 0)
                       as reserved_micro_usd,
                     COALESCE(SUM(CASE WHEN status IN ('reserved', 'settled', 'uncertain') THEN
                       CASE WHEN status = 'settled' THEN settled_micro_usd ELSE reserved_micro_usd END
                     ELSE 0 END), 0) as total_micro_usd
                   FROM operations"""
            )
            row = cur.fetchone()
            if not row:
                return {"settled_micro_usd": 0, "reserved_micro_usd": 0, "total_micro_usd": 0}
            return {
                "settled_micro_usd": row[0],
                "reserved_micro_usd": row[1],
                "total_micro_usd": row[2],
            }

    def reserve_budget(
        self,
        run_id: str,
        operation_id: str,
        kind: str,
        estimated_usd: float,
        global_budget_usd: Optional[float] = None,
    ) -> Dict[str, Any]:
        if estimated_usd < 0:
            raise StorageError("invalid_request", "reserved_micro_usd must be non-negative", 400)

        reserved_micro_usd = int(estimated_usd * 1_000_000)
        global_cap = int((global_budget_usd if global_budget_usd is not None else 25.0) * 1_000_000)
        now = _now_iso()

        with self._op_lock():
            cur = self._conn.execute("SELECT max_run_micro_usd FROM runs WHERE run_id = ?", (run_id,))
            run_row = cur.fetchone()
            if not run_row:
                raise StorageNotFoundError("not_found", f"Run '{run_id}' not found")

            max_run_micro_usd = run_row[0]

            res = self._conn.execute(
                """INSERT INTO operations (
                     operation_id, run_id, kind, status, reserved_micro_usd,
                     settled_micro_usd, provider_ref, created_at, updated_at
                   )
                   SELECT ?, ?, ?, 'reserved', ?, NULL, NULL, ?, ?
                   WHERE (
                     SELECT COALESCE(SUM(
                       CASE WHEN status = 'settled' THEN settled_micro_usd ELSE reserved_micro_usd END
                     ), 0)
                     FROM operations
                     WHERE run_id = ? AND status IN ('reserved', 'settled', 'uncertain')
                   ) + ? <= ?
                   AND (
                     SELECT COALESCE(SUM(
                       CASE WHEN status = 'settled' THEN settled_micro_usd ELSE reserved_micro_usd END
                     ), 0)
                     FROM operations
                     WHERE status IN ('reserved', 'settled', 'uncertain')
                   ) + ? <= ?""",
                (
                    operation_id,
                    run_id,
                    kind,
                    reserved_micro_usd,
                    now,
                    now,
                    run_id,
                    reserved_micro_usd,
                    max_run_micro_usd,
                    reserved_micro_usd,
                    global_cap,
                ),
            )
            if res.rowcount == 0:
                raise StorageConflictError(
                    "budget_limit_exceeded",
                    "Requested reservation exceeds available budget cap",
                )

            self._conn.commit()

        return {"ok": True}

    def settle_budget(
        self,
        operation_id: str,
        actual_usd: float,
    ) -> Dict[str, Any]:
        if actual_usd < 0:
            raise StorageError("invalid_request", "settled_micro_usd must be non-negative", 400)

        settled_micro = int(actual_usd * 1_000_000)
        now = _now_iso()

        with self._op_lock():
            cur = self._conn.execute(
                "SELECT operation_id, status, settled_micro_usd FROM operations WHERE operation_id = ?",
                (operation_id,),
            )
            row = cur.fetchone()
            if not row:
                raise StorageNotFoundError("not_found", f"Operation '{operation_id}' not found")

            status = row[1]
            existing_settled = row[2]

            if status == "settled":
                if existing_settled != settled_micro:
                    raise StorageConflictError(
                        "operation_already_settled",
                        "Operation is already settled with a different amount",
                    )
                return {"ok": True}

            if status not in ("reserved", "uncertain"):
                raise StorageConflictError("invalid_state", f"Cannot settle operation in '{status}' state")

            self._conn.execute(
                "UPDATE operations SET settled_micro_usd = ?, status = 'settled', updated_at = ? "
                "WHERE operation_id = ?",
                (settled_micro, now, operation_id),
            )
            self._conn.commit()

        return {"ok": True}

    def record_provider_ref(
        self,
        operation_id: str,
        provider_ref: str,
    ) -> Dict[str, Any]:
        now = _now_iso()

        with self._op_lock():
            cur = self._conn.execute("SELECT status FROM operations WHERE operation_id = ?", (operation_id,))
            row = cur.fetchone()
            if not row:
                raise StorageNotFoundError("not_found", f"Operation '{operation_id}' not found")

            status = row[0]
            if status not in ("reserved", "uncertain"):
                raise StorageConflictError(
                    "invalid_state",
                    f"Cannot update provider_ref for operation in '{status}' state",
                )

            self._conn.execute(
                "UPDATE operations SET provider_ref = ?, updated_at = ? WHERE operation_id = ?",
                (provider_ref, now, operation_id),
            )
            self._conn.commit()

        return {"ok": True}

    def cleanup_manifest(self, manifest: Dict[str, List[str]]) -> Dict[str, Any]:
        task_ids = [str(x) for x in manifest.get("tasks", []) if isinstance(x, str)]
        run_ids = [str(x) for x in manifest.get("runs", []) if isinstance(x, str)]
        op_ids = [str(x) for x in manifest.get("operations", []) if isinstance(x, str)]
        art_ids = [str(x) for x in manifest.get("artifacts", []) if isinstance(x, str)]

        deleted = {"operations": 0, "artifacts": 0, "events": 0, "runs": 0, "tasks": 0}

        def chunk(lst: List[str], sz: int = 50) -> List[List[str]]:
            return [lst[i:i + sz] for i in range(0, len(lst), sz)]

        with self._op_lock():
            for b in chunk(op_ids):
                q = ",".join(["?"] * len(b))
                res = self._conn.execute(f"DELETE FROM operations WHERE operation_id IN ({q})", tuple(b))
                deleted["operations"] += res.rowcount

            for b in chunk(art_ids):
                q = ",".join(["?"] * len(b))
                res = self._conn.execute(f"DELETE FROM artifacts WHERE artifact_id IN ({q})", tuple(b))
                deleted["artifacts"] += res.rowcount

            for b in chunk(run_ids):
                q = ",".join(["?"] * len(b))
                res_e = self._conn.execute(f"DELETE FROM events WHERE run_id IN ({q})", tuple(b))
                deleted["events"] += res_e.rowcount
                res_r = self._conn.execute(f"DELETE FROM runs WHERE run_id IN ({q})", tuple(b))
                deleted["runs"] += res_r.rowcount

            for b in chunk(task_ids):
                q = ",".join(["?"] * len(b))
                res_t = self._conn.execute(f"DELETE FROM tasks WHERE task_id IN ({q})", tuple(b))
                deleted["tasks"] += res_t.rowcount

            self._conn.commit()

        return {"ok": True, "deleted": deleted}


if __name__ == "__main__":
    import sys

    client = TursoClient()
    args = sys.argv[1:]
    if not args or args[0] == "health":
        print(json.dumps(client.health()))
    elif args[0] == "seed-run" and len(args) >= 6:
        run_id, task_id, mode, search_mode, state = args[1:6]
        res = client.create_run(run_id=run_id, task_id=task_id, mode=mode, search_mode=search_mode, state=state)
        print(json.dumps(res))
    elif args[0] == "get-run" and len(args) >= 2:
        run_id = args[1]
        print(json.dumps(client.get_run(run_id)))
    elif args[0] == "reserve-budget" and len(args) >= 5:
        run_id, op_id, kind, est = args[1:5]
        res = client.reserve_budget(run_id=run_id, operation_id=op_id, kind=kind, estimated_usd=float(est))
        print(json.dumps(res))
    elif args[0] == "budget-usage":
        print(json.dumps(client.get_budget_usage()))
    else:
        print(f"Unknown command: {args}")
        sys.exit(1)
