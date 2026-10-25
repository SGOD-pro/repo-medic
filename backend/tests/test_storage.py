import pytest
import sqlite3
import threading
import json
import base64
import hashlib
import re
from typing import Any, Dict, List, Optional
import httpx

from src.contracts import (
    RepairRequest,
    TaskRecipe,
    RunSummary,
    EventEnvelope,
    ArtifactSummary,
)
from src.engine.fake_engine import repair
from src.storage.db_client import RepoMedicDB
from src.storage.repository import D1StorageRepository, D1HostPorts


def create_sqlite_d1_transport(expected_token: str = "test-token") -> httpx.BaseTransport:
    """Creates an in-memory SQLite transport that simulates the Cloudflare D1 Worker bridge."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row

    # Initialize schema matching 0001_initial_schema.sql
    conn.executescript("""
    CREATE TABLE runs (
      run_id TEXT PRIMARY KEY,
      task_id TEXT NOT NULL,
      mode TEXT NOT NULL,
      search_mode TEXT NOT NULL,
      state TEXT NOT NULL,
      reason TEXT,
      usage_json TEXT NOT NULL,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      max_run_micro_usd INTEGER NOT NULL CHECK (max_run_micro_usd >= 0)
    );

    CREATE TABLE events (
      run_id TEXT NOT NULL REFERENCES runs(run_id),
      seq INTEGER NOT NULL CHECK (seq >= 1),
      ts TEXT NOT NULL,
      type TEXT NOT NULL,
      payload_json TEXT NOT NULL,
      PRIMARY KEY (run_id, seq)
    );

    CREATE TABLE artifacts (
      artifact_id TEXT PRIMARY KEY,
      run_id TEXT NOT NULL REFERENCES runs(run_id),
      kind TEXT NOT NULL,
      filename TEXT NOT NULL,
      sha256 TEXT NOT NULL,
      size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
      content_base64 TEXT NOT NULL,
      created_at TEXT NOT NULL
    );

    CREATE TABLE operations (
      operation_id TEXT PRIMARY KEY,
      run_id TEXT NOT NULL REFERENCES runs(run_id),
      kind TEXT NOT NULL,
      status TEXT NOT NULL,
      reserved_micro_usd INTEGER NOT NULL CHECK (reserved_micro_usd >= 0),
      settled_micro_usd INTEGER CHECK (settled_micro_usd >= 0),
      provider_ref TEXT,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
    );

    CREATE TABLE tasks (
      task_id TEXT PRIMARY KEY,
      title TEXT NOT NULL,
      repository_url TEXT NOT NULL,
      commit_sha TEXT NOT NULL,
      dependency TEXT NOT NULL,
      from_version TEXT NOT NULL,
      to_version TEXT NOT NULL,
      recipe_json TEXT,
      created_at TEXT NOT NULL
    );
    """)

    lock = threading.Lock()

    def _sync_handler(request: httpx.Request) -> httpx.Response:
        url = request.url
        method = request.method.upper()
        path = url.path.rstrip("/")

        if method == "GET" and path == "/health":
            return httpx.Response(200, json={"ok": True, "status": "healthy"})

        auth = request.headers.get("Authorization")
        if not auth or auth != f"Bearer {expected_token}":
            return httpx.Response(401, json={"error": {"code": "unauthorized", "message": "Unauthorized"}})

        # GET /api/tasks
        if method == "GET" and path == "/api/tasks":
            rows = conn.execute(
                "SELECT task_id, title, repository_url, commit_sha, dependency, "
                "from_version, to_version, recipe_json FROM tasks ORDER BY created_at ASC"
            ).fetchall()
            return httpx.Response(200, json={"tasks": [dict(r) for r in rows]})

        # POST /api/tasks
        if method == "POST" and path == "/api/tasks":
            body = json.loads(request.content.decode("utf-8"))
            for field in [
                "task_id",
                "title",
                "repository_url",
                "commit_sha",
                "dependency",
                "from_version",
                "to_version",
            ]:
                if field not in body:
                    return httpx.Response(
                        400,
                        json={"error": {"code": "invalid_request", "message": "Missing required task fields"}},
                    )
            recipe_json = body.get("recipe_json")
            if isinstance(recipe_json, dict):
                recipe_json = json.dumps(recipe_json)
            conn.execute(
                """INSERT INTO tasks (
                     task_id, title, repository_url, commit_sha, dependency,
                     from_version, to_version, recipe_json, created_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, '2026-10-10T00:00:00Z')
                   ON CONFLICT(task_id) DO UPDATE SET
                     title = excluded.title,
                     repository_url = excluded.repository_url,
                     commit_sha = excluded.commit_sha,
                     dependency = excluded.dependency,
                     from_version = excluded.from_version,
                     to_version = excluded.to_version,
                     recipe_json = excluded.recipe_json""",
                (
                    body["task_id"],
                    body["title"],
                    body["repository_url"],
                    body["commit_sha"],
                    body["dependency"],
                    body["from_version"],
                    body["to_version"],
                    recipe_json,
                ),
            )
            return httpx.Response(201, json={"ok": True, "task_id": body["task_id"]})

        # GET /api/tasks/:task_id
        task_match = re.match(r"^/api/tasks/([^/]+)$", path)
        if method == "GET" and task_match:
            t_id = task_match.group(1)
            row = conn.execute(
                "SELECT task_id, title, repository_url, commit_sha, dependency, "
                "from_version, to_version, recipe_json FROM tasks WHERE task_id = ?",
                (t_id,),
            ).fetchone()
            if not row:
                return httpx.Response(404, json={"error": {"code": "not_found", "message": "Task not found"}})
            return httpx.Response(200, json=dict(row))

        # GET /api/runs (list)
        if method == "GET" and path == "/api/runs":
            limit_val = int(request.url.params.get("limit", 50))
            task_filter = request.url.params.get("task_id")
            state_filter = request.url.params.get("state")
            run_prefix = request.url.params.get("run_prefix")
            if state_filter and state_filter not in ["queued", "running", "succeeded", "failed", "cancelled"]:
                return httpx.Response(
                    400,
                    json={"error": {"code": "invalid_state", "message": f"Invalid state filter '{state_filter}'"}},
                )
            query = (
                "SELECT run_id, task_id, mode, search_mode, state, reason, usage_json, created_at, "
                "max_run_micro_usd FROM runs"
            )
            params = []
            conditions = []
            if task_filter:
                conditions.append("task_id = ?")
                params.append(task_filter)
            if state_filter:
                conditions.append("state = ?")
                params.append(state_filter)
            if run_prefix:
                escaped_prefix = run_prefix.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                conditions.append("run_id LIKE ? ESCAPE '\\'")
                params.append(f"{escaped_prefix}%")
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            if state_filter == "queued":
                query += " ORDER BY created_at ASC, run_id ASC LIMIT ?"
            else:
                query += " ORDER BY created_at DESC, run_id ASC LIMIT ?"
            params.append(limit_val)
            rows = conn.execute(query, params).fetchall()
            # Batch query artifacts by run id to avoid N+1 queries
            run_ids = [r["run_id"] for r in rows]
            artifacts_by_run: Dict[str, List[Dict[str, Any]]] = {rid: [] for rid in run_ids}
            if run_ids:
                placeholders = ",".join("?" * len(run_ids))
                art_rows = conn.execute(
                    f"SELECT artifact_id, kind, filename, run_id FROM artifacts WHERE run_id IN ({placeholders})",
                    run_ids,
                ).fetchall()
                for a in art_rows:
                    artifacts_by_run[a["run_id"]].append({
                        "artifact_id": a["artifact_id"],
                        "kind": a["kind"],
                        "filename": a["filename"],
                    })

            runs_list = []
            for r in rows:
                cur_ops = conn.execute(
                    "SELECT COALESCE(SUM(CASE WHEN status = 'settled' "
                    "THEN settled_micro_usd ELSE reserved_micro_usd END), 0) "
                    "FROM operations WHERE run_id = ? AND status IN ('reserved', 'settled', 'uncertain')",
                    (r["run_id"],),
                )
                ops_micro = cur_ops.fetchone()[0] or 0
                usage = json.loads(r["usage_json"])
                if ops_micro > 0 or usage.get("estimated_usd", 0.0) == 0.0:
                    usage["estimated_usd"] = ops_micro / 1_000_000.0

                cur_model_ops = conn.execute(
                    "SELECT COUNT(*) FROM operations WHERE run_id = ? AND kind = 'model' "
                    "AND status IN ('reserved', 'settled', 'uncertain')",
                    (r["run_id"],),
                )
                model_ops_count = cur_model_ops.fetchone()[0] or 0
                if model_ops_count > 0 and usage.get("model_calls", 0) == 0:
                    usage["model_calls"] = model_ops_count

                runs_list.append({
                    "run_id": r["run_id"],
                    "task_id": r["task_id"],
                    "mode": r["mode"],
                    "search_mode": r["search_mode"],
                    "state": r["state"],
                    "reason": r["reason"],
                    "max_run_micro_usd": r["max_run_micro_usd"],
                    "usage": usage,
                    "artifacts": artifacts_by_run.get(r["run_id"], []),
                })
            return httpx.Response(200, json={"runs": runs_list})

        # POST /api/runs
        if method == "POST" and path == "/api/runs":
            body = json.loads(request.content.decode("utf-8"))
            run_id = body.get("run_id")
            if not run_id or not isinstance(run_id, str) or not re.match(r"^[a-zA-Z0-9_-]{1,128}$", run_id):
                return httpx.Response(
                    400,
                    json={
                        "error": {
                            "code": "invalid_request",
                            "message": "Invalid run_id format: must be 1-128 characters matching [a-zA-Z0-9_-]",
                        }
                    },
                )
            row = conn.execute("SELECT 1 FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            if row:
                return httpx.Response(409, json={"error": {"code": "run_already_exists", "message": "Exists"}})
            initial_usage = json.dumps(
                {"model_calls": 0, "input_tokens": 0, "output_tokens": 0, "estimated_usd": 0}
            )
            created_at_val = body.get("created_at", "2026-10-10T00:00:00Z")
            updated_at_val = body.get("updated_at", created_at_val)
            conn.execute(
                "INSERT INTO runs VALUES (?, ?, ?, ?, ?, NULL, ?, ?, ?, ?)",
                (
                    run_id,
                    body["task_id"],
                    body["mode"],
                    body["search_mode"],
                    body.get("state", "queued"),
                    initial_usage,
                    created_at_val,
                    updated_at_val,
                    body.get("max_run_micro_usd", 0),
                ),
            )
            return httpx.Response(201, json={"ok": True, "run_id": run_id})

        # GET /api/runs/:run_id
        is_subpath = any(p in path for p in ["/events", "/artifacts", "/operations"])
        is_run_detail = method == "GET" and path.startswith("/api/runs/") and not is_subpath
        if is_run_detail:
            run_id = path.split("/")[-1]
            row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            if not row:
                return httpx.Response(404, json={"error": {"code": "not_found", "message": "Not found"}})
            arts = conn.execute(
                "SELECT artifact_id, kind, filename FROM artifacts WHERE run_id = ?", (run_id,)
            ).fetchall()
            cur_ops = conn.execute(
                "SELECT COALESCE(SUM(CASE WHEN status = 'settled' "
                "THEN settled_micro_usd ELSE reserved_micro_usd END), 0) "
                "FROM operations WHERE run_id = ? AND status IN ('reserved', 'settled', 'uncertain')",
                (run_id,),
            )
            ops_micro = cur_ops.fetchone()[0] or 0
            usage = json.loads(row["usage_json"])
            if ops_micro > 0 or usage.get("estimated_usd", 0.0) == 0.0:
                usage["estimated_usd"] = ops_micro / 1_000_000.0

            cur_model_ops = conn.execute(
                "SELECT COUNT(*) FROM operations WHERE run_id = ? AND kind = 'model' "
                "AND status IN ('reserved', 'settled', 'uncertain')",
                (row["run_id"],),
            )
            model_ops_count = cur_model_ops.fetchone()[0] or 0
            if model_ops_count > 0 and usage.get("model_calls", 0) == 0:
                usage["model_calls"] = model_ops_count

            return httpx.Response(200, json={
                "run_id": row["run_id"],
                "task_id": row["task_id"],
                "mode": row["mode"],
                "search_mode": row["search_mode"],
                "state": row["state"],
                "reason": row["reason"],
                "max_run_micro_usd": row["max_run_micro_usd"],
                "usage": usage,
                "artifacts": [dict(a) for a in arts],
            })

        # PATCH /api/runs/:run_id
        run_match = re.match(r"^/api/runs/([^/]+)$", path)
        if method == "PATCH" and run_match:
            run_id = run_match.group(1)
            body = json.loads(request.content.decode("utf-8"))
            row = conn.execute("SELECT state FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            if not row:
                return httpx.Response(404, json={"error": {"code": "not_found", "message": "Not found"}})
            if row["state"] in ["succeeded", "failed", "cancelled"]:
                return httpx.Response(409, json={"error": {"code": "terminal_state_immutable", "message": "Imm"}})
            if "from_state" in body and row["state"] != body["from_state"]:
                return httpx.Response(409, json={"error": {"code": "state_conflict", "message": "State conflict"}})
            conn.execute(
                "UPDATE runs SET state = ?, reason = ? WHERE run_id = ?",
                (body["state"], body.get("reason"), run_id),
            )
            return httpx.Response(200, json={"ok": True})

        # POST /api/runs/:run_id/events
        if method == "POST" and path.endswith("/events") and path.startswith("/api/runs/"):
            run_id = path.split("/")[3]
            body = json.loads(request.content.decode("utf-8"))
            if not body.get("type") or not isinstance(body.get("type"), str):
                return httpx.Response(400, json={"error": {"code": "invalid_request", "message": "Type required"}})
            if not body.get("payload") or not isinstance(body.get("payload"), dict):
                return httpx.Response(400, json={"error": {"code": "invalid_request", "message": "Payload required"}})
            row = conn.execute("SELECT 1 FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            if not row:
                return httpx.Response(404, json={"error": {"code": "not_found", "message": "Not found"}})
            max_seq = conn.execute(
                "SELECT COALESCE(MAX(seq), 0) + 1 AS next_seq FROM events WHERE run_id = ?",
                (run_id,),
            ).fetchone()["next_seq"]
            conn.execute(
                "INSERT INTO events VALUES (?, ?, '2026-10-10T00:00:00Z', ?, ?)",
                (run_id, max_seq, body["type"], json.dumps(body["payload"])),
            )
            if body["type"] == "usage.updated" and isinstance(body.get("payload"), dict):
                conn.execute(
                    "UPDATE runs SET usage_json = ? WHERE run_id = ?",
                    (json.dumps(body["payload"]), run_id),
                )
            return httpx.Response(201, json={"ok": True, "seq": max_seq, "ts": "2026-10-10T00:00:00Z"})

        # GET /api/runs/:run_id/events
        if method == "GET" and path.endswith("/events") and path.startswith("/api/runs/"):
            run_id = path.split("/")[3]
            row = conn.execute("SELECT 1 FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            if not row:
                return httpx.Response(404, json={"error": {"code": "not_found", "message": "Not found"}})
            after = int(url.params.get("after", 0))
            events = conn.execute(
                "SELECT seq, type, payload_json, ts FROM events WHERE run_id = ? AND seq > ? ORDER BY seq ASC",
                (run_id, after),
            ).fetchall()
            return httpx.Response(200, json={
                "events": [
                    {"seq": e["seq"], "type": e["type"], "payload": json.loads(e["payload_json"]), "ts": e["ts"]}
                    for e in events
                ]
            })

        # POST /api/runs/:run_id/artifacts
        if method == "POST" and path.endswith("/artifacts") and path.startswith("/api/runs/"):
            run_id = path.split("/")[3]
            body = json.loads(request.content.decode("utf-8"))
            if body["size_bytes"] > 1048576:
                return httpx.Response(
                    413, json={"error": {"code": "artifact_size_limit_exceeded", "message": "Too large"}}
                )
            tot = conn.execute(
                "SELECT COALESCE(SUM(size_bytes), 0) AS s FROM artifacts WHERE run_id = ?",
                (run_id,),
            ).fetchone()["s"]
            if tot + body["size_bytes"] > 8388608:
                return httpx.Response(
                    413, json={"error": {"code": "run_artifact_volume_limit_exceeded", "message": "Exceeded"}}
                )
            conn.execute(
                "INSERT INTO artifacts VALUES (?, ?, ?, ?, ?, ?, ?, '2026-10-10T00:00:00Z')",
                (
                    body["artifact_id"],
                    run_id,
                    body["kind"],
                    body["filename"],
                    body["sha256"],
                    body["size_bytes"],
                    body["content_base64"],
                ),
            )
            return httpx.Response(201, json={"ok": True, "artifact_id": body["artifact_id"]})

        # GET /api/runs/:run_id/artifacts/:artifact_id
        if method == "GET" and "/artifacts/" in path and path.startswith("/api/runs/"):
            parts = path.split("/")
            run_id = parts[3]
            art_id = parts[5]
            row = conn.execute(
                "SELECT * FROM artifacts WHERE run_id = ? AND artifact_id = ?",
                (run_id, art_id),
            ).fetchone()
            if not row:
                return httpx.Response(404, json={"error": {"code": "not_found", "message": "Not found"}})
            return httpx.Response(200, json=dict(row))

        # GET /api/budget/usage
        if method == "GET" and path == "/api/budget/usage":
            row = conn.execute(
                "SELECT "
                "COALESCE(SUM(CASE WHEN status = 'settled' THEN settled_micro_usd ELSE 0 END), 0) "
                "  AS settled_micro_usd, "
                "COALESCE(SUM(CASE WHEN status = 'reserved' THEN reserved_micro_usd ELSE 0 END), 0) "
                "  AS reserved_micro_usd, "
                "COALESCE(SUM(CASE WHEN status IN ('reserved', 'settled', 'uncertain') THEN "
                "  CASE WHEN status = 'settled' THEN settled_micro_usd ELSE reserved_micro_usd END "
                "ELSE 0 END), 0) AS total_micro_usd "
                "FROM operations"
            ).fetchone()
            return httpx.Response(200, json=dict(row))

        # POST /api/runs/:run_id/operations
        ops_post_match = re.match(r"^/api/runs/([^/]+)/operations$", path)
        if method == "POST" and ops_post_match:
            run_id = ops_post_match.group(1)
            body = json.loads(request.content.decode("utf-8"))
            run = conn.execute("SELECT max_run_micro_usd FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            if not run:
                return httpx.Response(404, json={"error": {"code": "not_found", "message": "Not found"}})
            comm = conn.execute(
                "SELECT COALESCE(SUM(CASE WHEN status = 'settled' THEN settled_micro_usd "
                "ELSE reserved_micro_usd END), 0) AS c FROM operations "
                "WHERE run_id = ? AND status IN ('reserved', 'settled', 'uncertain')",
                (run_id,)
            ).fetchone()["c"]
            global_cap = body.get("global_budget_micro_usd", 25000000)
            global_comm = conn.execute(
                "SELECT COALESCE(SUM(CASE WHEN status = 'settled' THEN settled_micro_usd "
                "ELSE reserved_micro_usd END), 0) AS c FROM operations "
                "WHERE status IN ('reserved', 'settled', 'uncertain')"
            ).fetchone()["c"]
            res_val = body["reserved_micro_usd"]
            if comm + res_val > run["max_run_micro_usd"] or global_comm + res_val > global_cap:
                return httpx.Response(
                    409, json={"error": {"code": "budget_limit_exceeded", "message": "Budget exceeded"}}
                )
            conn.execute(
                "INSERT INTO operations VALUES (?, ?, ?, 'reserved', ?, NULL, NULL, "
                "'2026-10-10T00:00:00Z', '2026-10-10T00:00:00Z')",
                (body["operation_id"], run_id, body["kind"], body["reserved_micro_usd"]),
            )
            return httpx.Response(201, json={"ok": True})

        # PATCH /api/operations/:operation_id
        op_match = re.match(r"^/api/operations/([^/]+)$", path)
        if method == "PATCH" and op_match:
            op_id = op_match.group(1)
            body = json.loads(request.content.decode("utf-8"))
            if "settled_micro_usd" not in body and "provider_ref" not in body:
                return httpx.Response(400, json={"error": {"code": "invalid_request", "message": "Missing fields"}})
            row = conn.execute(
                "SELECT status, settled_micro_usd, provider_ref FROM operations WHERE operation_id = ?",
                (op_id,)
            ).fetchone()
            if not row:
                return httpx.Response(404, json={"error": {"code": "not_found", "message": "Not found"}})
            if "settled_micro_usd" in body:
                if row["status"] == "settled":
                    if row["settled_micro_usd"] != body["settled_micro_usd"]:
                        return httpx.Response(
                            409,
                            json={"error": {"code": "operation_already_settled", "message": "Different amount"}}
                        )
                    return httpx.Response(200, json={"ok": True})
                if row["status"] not in ("reserved", "uncertain"):
                    return httpx.Response(
                        409,
                        json={"error": {"code": "invalid_state", "message": f"Cannot settle in {row['status']} state"}}
                    )
                conn.execute(
                    "UPDATE operations SET settled_micro_usd = ?, status = 'settled', "
                    "provider_ref = COALESCE(?, provider_ref) WHERE operation_id = ?",
                    (body["settled_micro_usd"], body.get("provider_ref"), op_id),
                )
            elif "provider_ref" in body:
                if row["status"] not in ("reserved", "uncertain"):
                    return httpx.Response(
                        409,
                        json={"error": {"code": "invalid_state", "message": f"Cannot update in {row['status']} state"}}
                    )
                conn.execute(
                    "UPDATE operations SET provider_ref = ? WHERE operation_id = ?",
                    (body["provider_ref"], op_id),
                )
            return httpx.Response(200, json={"ok": True})

        # PATCH /api/operations/:operation_id/provider_ref
        op_pref_match = re.match(r"^/api/operations/([^/]+)/provider_ref$", path)
        if method == "PATCH" and op_pref_match:
            op_id = op_pref_match.group(1)
            body = json.loads(request.content.decode("utf-8"))
            if "provider_ref" not in body or not isinstance(body["provider_ref"], str):
                return httpx.Response(
                    400, json={"error": {"code": "invalid_request", "message": "provider_ref required"}}
                )
            row = conn.execute(
                "SELECT status FROM operations WHERE operation_id = ?",
                (op_id,)
            ).fetchone()
            if not row:
                return httpx.Response(404, json={"error": {"code": "not_found", "message": "Not found"}})
            if row["status"] not in ("reserved", "uncertain"):
                return httpx.Response(
                    409,
                    json={"error": {"code": "invalid_state", "message": f"Cannot update in {row['status']} state"}}
                )
            conn.execute(
                "UPDATE operations SET provider_ref = ? WHERE operation_id = ?",
                (body["provider_ref"], op_id),
            )
            return httpx.Response(200, json={"ok": True})

        # POST /api/cleanup (exact manifest cleanup)
        if method == "POST" and path == "/api/cleanup":
            body = json.loads(request.content.decode("utf-8")) if request.content else {}
            task_ids = [str(x) for x in body.get("tasks", []) if isinstance(x, str)]
            run_ids = [str(x) for x in body.get("runs", []) if isinstance(x, str)]
            op_ids = [str(x) for x in body.get("operations", []) if isinstance(x, str)]
            art_ids = [str(x) for x in body.get("artifacts", []) if isinstance(x, str)]

            deleted = {"operations": 0, "artifacts": 0, "events": 0, "runs": 0, "tasks": 0}

            if op_ids:
                q_marks = ",".join("?" * len(op_ids))
                cur = conn.execute(f"DELETE FROM operations WHERE operation_id IN ({q_marks})", op_ids)
                deleted["operations"] = cur.rowcount
            if art_ids:
                q_marks = ",".join("?" * len(art_ids))
                cur = conn.execute(f"DELETE FROM artifacts WHERE artifact_id IN ({q_marks})", art_ids)
                deleted["artifacts"] = cur.rowcount
            if run_ids:
                q_marks = ",".join("?" * len(run_ids))
                cur_ev = conn.execute(f"DELETE FROM events WHERE run_id IN ({q_marks})", run_ids)
                deleted["events"] = cur_ev.rowcount
                cur_runs = conn.execute(f"DELETE FROM runs WHERE run_id IN ({q_marks})", run_ids)
                deleted["runs"] = cur_runs.rowcount
            if task_ids:
                q_marks = ",".join("?" * len(task_ids))
                cur_tasks = conn.execute(f"DELETE FROM tasks WHERE task_id IN ({q_marks})", task_ids)
                deleted["tasks"] = cur_tasks.rowcount

            return httpx.Response(200, json={"ok": True, "deleted": deleted})

        return httpx.Response(404, json={"error": {"code": "not_found", "message": "Route not found"}})

    def handler(request: httpx.Request) -> httpx.Response:
        with lock:
            return _sync_handler(request)

    return httpx.MockTransport(handler)


@pytest.fixture
def mock_db():
    transport = create_sqlite_d1_transport(expected_token="secret-token")
    return RepoMedicDB(
        base_url="http://test-bridge",
        api_key="secret-token",
        transport=transport,
    )


def test_db_client_health_and_auth(mock_db):
    assert mock_db.health() == {"ok": True, "status": "healthy"}

    # Unauthorized access check
    bad_db = RepoMedicDB(
        base_url="http://test-bridge",
        api_key="wrong-key",
        transport=mock_db.transport,
    )
    with pytest.raises(httpx.HTTPStatusError) as exc:
        bad_db.get_run("any")
    assert exc.value.response.status_code == 401


def test_db_client_create_run_invalid_id_rejected(mock_db):
    with pytest.raises(httpx.HTTPStatusError) as exc:
        mock_db.create_run(
            run_id="run/invalid/id",
            task_id="task-1",
            mode="offline",
            search_mode="sequential",
        )
    assert exc.value.response.status_code == 400
    assert exc.value.response.json()["error"]["code"] == "invalid_request"


def test_db_client_runs_lifecycle(mock_db):
    # 1. Create run
    res = mock_db.create_run(
        run_id="run-1",
        task_id="task-1",
        mode="offline",
        search_mode="sequential",
        max_run_usd=1.5,
    )
    assert res == {"ok": True, "run_id": "run-1"}

    # 2. Get run
    data = mock_db.get_run("run-1")
    assert data["run_id"] == "run-1"
    assert data["state"] == "queued"
    assert data["artifacts"] == []

    # 3. Transition to running
    mock_db.update_run_state("run-1", state="running")
    assert mock_db.get_run("run-1")["state"] == "running"

    # 4. Transition to terminal state (succeeded)
    mock_db.update_run_state("run-1", state="succeeded")
    assert mock_db.get_run("run-1")["state"] == "succeeded"

    # 5. Immutable terminal state: trying to transition from succeeded raises 409
    with pytest.raises(httpx.HTTPStatusError) as exc:
        mock_db.update_run_state("run-1", state="running")
    assert exc.value.response.status_code == 409


def test_db_client_events_atomic_sequencing(mock_db):
    mock_db.create_run("run-events", "t1", "offline", "sequential", max_run_usd=1.0)

    e1 = mock_db.create_event(
        "run-events",
        "run.started",
        {"mode": "offline", "search_mode": "sequential", "max_run_usd": 1.0},
    )
    assert e1["seq"] == 1

    e2 = mock_db.create_event(
        "run-events",
        "stage.completed",
        {"stage": "baseline", "passed": True, "summary": "ok"},
    )
    assert e2["seq"] == 2

    # Fetch ordered events
    events = mock_db.list_events("run-events")
    assert len(events) == 2
    assert [e["seq"] for e in events] == [1, 2]

    # Fetch with cursor
    after_1 = mock_db.list_events("run-events", after=1)
    assert len(after_1) == 1
    assert after_1[0]["seq"] == 2


def test_db_client_artifacts_bounds(mock_db):
    mock_db.create_run("run-art", "t1", "offline", "sequential", max_run_usd=1.0)

    # 1. Store valid artifact
    content = b"diff --git a/file b/file\n+new line"
    sha = hashlib.sha256(content).hexdigest()
    b64 = base64.b64encode(content).decode("ascii")

    res = mock_db.store_artifact(
        run_id="run-art",
        artifact_id="art-1",
        kind="patch",
        filename="repair.patch",
        sha256=sha,
        size_bytes=len(content),
        content_base64=b64,
    )
    assert res == {"ok": True, "artifact_id": "art-1"}

    # Retrieve artifact
    fetched = mock_db.get_artifact("run-art", "art-1")
    assert fetched["filename"] == "repair.patch"
    assert fetched["sha256"] == sha

    # 2. Reject artifact exceeding 1MB limit
    with pytest.raises(httpx.HTTPStatusError) as exc:
        mock_db.store_artifact(
            run_id="run-art",
            artifact_id="art-huge",
            kind="log",
            filename="huge.log",
            sha256="abc",
            size_bytes=1048577,
            content_base64="abc",
        )
    assert exc.value.response.status_code == 413


def test_db_client_budget_reservation_limits(mock_db):
    # Max budget: 1.0 USD = 1,000,000 micro USD
    mock_db.create_run("run-budget", "t1", "offline", "sequential", max_run_usd=1.0)

    # 1. Reserve 0.4 USD (valid)
    assert mock_db.reserve_budget("run-budget", "model:1", "model", estimated_usd=0.4)["ok"] is True

    # 2. Settle 0.3 USD
    assert mock_db.settle_budget("model:1", actual_usd=0.3)["ok"] is True

    # 2a. Idempotent re-settle with identical amount succeeds
    assert mock_db.settle_budget("model:1", actual_usd=0.3)["ok"] is True

    # 2b. Conflicting re-settle with different amount fails with 409
    with pytest.raises(httpx.HTTPStatusError) as exc:
        mock_db.settle_budget("model:1", actual_usd=0.5)
    assert exc.value.response.status_code == 409

    # 2c. Empty PATCH body fails with 400
    with pytest.raises(httpx.HTTPStatusError) as exc:
        mock_db._request("PATCH", "/api/operations/model:1", json={})
    assert exc.value.response.status_code == 400

    # 3. Reserve 0.6 USD (valid: 0.3 settled + 0.6 reserved = 0.9 <= 1.0)
    assert mock_db.reserve_budget("run-budget", "model:2", "model", estimated_usd=0.6)["ok"] is True

    # 4. Attempt to reserve another 0.2 USD (0.3 + 0.6 + 0.2 = 1.1 > 1.0) -> 409 Conflict
    with pytest.raises(httpx.HTTPStatusError) as exc:
        mock_db.reserve_budget("run-budget", "model:3", "model", estimated_usd=0.2)
    assert exc.value.response.status_code == 409


@pytest.mark.asyncio
async def test_repository_and_hostports_with_fake_engine(mock_db):
    repo = D1StorageRepository(mock_db)

    # 1. Create run through repository
    run = repo.create_run("run-engine-test", "task-1", "offline", "sequential", max_run_usd=2.0)
    assert isinstance(run, RunSummary)
    assert run.run_id == "run-engine-test"
    assert run.state == "queued"

    # 2. Wire D1HostPorts and execute FakeEngine repair
    host = D1HostPorts(run_id="run-engine-test", client=mock_db)

    dummy_request = RepairRequest(
        run_id="run-engine-test",
        task_id="task-1",
        mode="offline",
        search_mode="sequential",
        max_run_usd=2.0,
    )
    dummy_recipe = TaskRecipe(
        task_id="task-1",
        title="Test Recipe",
        repository_url="https://github.com/example/repo",
        commit_sha="123456",
        dependency="pytest",
        from_version="7.0.0",
        to_version="8.0.0",
        test_command=["pytest"],
        allowed_source_paths=["src/"],
        expected_failure="Error",
        timeout_seconds=60,
        max_candidates=1,
        max_refinements=0,
    )

    result = await repair(dummy_request, dummy_recipe, host)
    assert result.state == "succeeded"

    # 3. Verify events were persisted into D1
    events = repo.list_events("run-engine-test")
    assert len(events) > 0
    for e in events:
        assert isinstance(e, EventEnvelope)
        assert e.run_id == "run-engine-test"
        assert e.seq >= 1

    # Verify FakeEngine never emitted run.finished (Package B owns run.finished)
    event_types = [e.type for e in events]
    assert "run.finished" not in event_types

    # 4. Final transition owned by B
    repo.update_run_state("run-engine-test", state="succeeded")
    final_run = repo.get_run("run-engine-test")
    assert final_run.state == "succeeded"


def test_db_client_and_repository_tasks(mock_db):
    repo = D1StorageRepository(mock_db)

    # 1. Empty tasks list initially
    assert repo.list_tasks() == []
    assert repo.get_task("task-unknown") is None

    # 2. Upsert task
    task_payload = {
        "task_id": "example-task-1",
        "title": "Upgrade pytest-mock",
        "repository_url": "https://github.com/example/repo",
        "commit_sha": "abcdef123456",
        "dependency": "pytest-mock",
        "from_version": "3.10.0",
        "to_version": "3.11.1",
        "recipe_json": {"test_command": ["pytest"]},
    }
    repo.upsert_task(task_payload)

    # 3. Get task
    task = repo.get_task("example-task-1")
    assert task is not None
    assert task.task_id == "example-task-1"
    assert task.dependency == "pytest-mock"

    # 4. List tasks
    all_tasks = repo.list_tasks()
    assert len(all_tasks) == 1
    assert all_tasks[0].task_id == "example-task-1"


def test_db_client_and_repository_list_runs(mock_db):
    repo = D1StorageRepository(mock_db)

    # Create two runs for different tasks
    repo.create_run("run-101", "task-a", "offline", "sequential", max_run_usd=1.0)
    repo.create_run("run-102", "task-b", "offline", "branch_refine", max_run_usd=2.0)

    # List all runs
    runs = repo.list_runs(limit=10)
    assert len(runs) == 2

    # Filter by task_id
    filtered = repo.list_runs(limit=10, task_id="task-a")
    assert len(filtered) == 1
    assert filtered[0].run_id == "run-101"

    # State filter validation
    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        repo.list_runs(limit=10, state="bogus")
    assert exc_info.value.response.status_code == 400


def test_update_run_state_from_state_cas(mock_db):
    mock_db.create_run("run-cas", "task-1", "offline", "sequential")

    # Mismatch from_state -> 409
    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        mock_db.update_run_state("run-cas", state="running", from_state="failed")
    assert exc_info.value.response.status_code == 409

    # Matching from_state -> 200
    res = mock_db.update_run_state("run-cas", state="running", from_state="queued")
    assert res.get("ok") is True


@pytest.mark.asyncio
async def test_d1_hostports_cancelled_error_handling(mock_db):
    from unittest.mock import MagicMock
    from src.storage.repository import D1HostPorts

    # 1. Normal run - not cancelled
    mock_db.create_run("run-cancel-test", "task-1", "offline", "sequential")
    hp = D1HostPorts("run-cancel-test", client=mock_db)
    assert await hp.cancelled() is False

    # 2. Cancelled run
    mock_db.update_run_state("run-cancel-test", state="cancelled")
    assert await hp.cancelled() is True

    # 3. 404 on get_run returns False
    hp_not_found = D1HostPorts("run-non-existent", client=mock_db)
    assert await hp_not_found.cancelled() is False

    # 4. 500 error raises HTTPStatusError
    failing_client = MagicMock()
    req = httpx.Request("GET", "http://test/api/runs/bad")
    resp = httpx.Response(500, request=req)
    failing_client.get_run.side_effect = httpx.HTTPStatusError("Server Error", request=req, response=resp)
    hp_failing = D1HostPorts("bad", client=failing_client)

    with pytest.raises(httpx.HTTPStatusError):
        await hp_failing.cancelled()


@pytest.mark.asyncio
async def test_atomic_global_budget_enforcement_across_runs(mock_db):
    repo = D1StorageRepository(mock_db)

    # Create two concurrent runs
    mock_db.create_run("run-budget-1", "task-1", "offline", "sequential", max_run_usd=25.0)
    mock_db.create_run("run-budget-2", "task-2", "offline", "sequential", max_run_usd=25.0)

    hp1 = D1HostPorts("run-budget-1", client=mock_db)
    hp2 = D1HostPorts("run-budget-2", client=mock_db)

    # Run 1 reserves $20.00 (within $25.00 total) -> success
    ok1 = await hp1.reserve("model:gen1", 20.00)
    assert ok1 is True

    # Run 2 tries to reserve $10.00 ($20.00 + $10.00 = $30.00 > $25.00 total) -> denied
    ok2 = await hp2.reserve("model:gen2", 10.00)
    assert ok2 is False

    # Check committed usage
    assert repo.get_total_committed_usd() == 20.00

    # Run 1 settles to actual cost of $5.00
    await hp1.settle("model:gen1", 5.00)
    assert repo.get_total_committed_usd() == 5.00

    # Now Run 2 can reserve $10.00 ($5.00 + $10.00 = $15.00 <= $25.00) -> success
    ok2_retry = await hp2.reserve("model:gen2", 10.00)
    assert ok2_retry is True
    assert repo.get_total_committed_usd() == 15.00


@pytest.mark.asyncio
async def test_run_usage_derived_from_operation_ledger_prevents_zero_summary(mock_db):
    """Regression test: run usage estimated_usd must derive from operation ledger, not stay zero."""
    repo = D1StorageRepository(mock_db)
    run_id = "run-reconcile-ops-1"

    mock_db.create_run(run_id, "TASK-091", "live", "sequential", max_run_usd=2.0)
    hp = D1HostPorts(run_id, client=mock_db)

    # Initial usage before operations
    initial_run = repo.get_run(run_id)
    assert initial_run.usage.estimated_usd == 0.0
    assert initial_run.usage.model_calls == 0

    # Execute and settle three operations mirroring live repair: setup (0.20), model (0.05), verify (0.10)
    assert await hp.reserve("sandbox:setup", 0.20) is True
    await hp.settle("sandbox:setup", 0.20)

    assert await hp.reserve("candidate_gen_candidate_1", 0.05) is True
    await hp.settle("candidate_gen_candidate_1", 0.05)

    assert await hp.reserve("sandbox:verify_candidate_1", 0.10) is True
    await hp.settle("sandbox:verify_candidate_1", 0.10)

    # Reconciled get_run must reflect $0.3500 from the operation ledger, not 0.0
    reconciled_run = repo.get_run(run_id)
    assert reconciled_run.usage.estimated_usd == 0.35
    assert reconciled_run.usage.estimated_usd > 0.0, "Run summary must not remain zero when operations are settled"

    # Reconciled model calls derive from committed model operations in the ledger
    assert reconciled_run.usage.model_calls == 1, "Run that performed model inference must not report zero calls"
    assert reconciled_run.usage.input_tokens == 0
    assert reconciled_run.usage.output_tokens == 0

    # list_runs must also derive the same estimated allocation
    runs_list = repo.list_runs(run_prefix=run_id)
    assert len(runs_list) == 1
    assert runs_list[0].usage.estimated_usd == 0.35
