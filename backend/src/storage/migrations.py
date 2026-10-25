import logging
from typing import Any

logger = logging.getLogger("repomedic.storage.migrations")

MIGRATION_0001 = """
CREATE TABLE IF NOT EXISTS runs (
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

CREATE INDEX IF NOT EXISTS idx_runs_state_created_at ON runs(state, created_at);

CREATE TABLE IF NOT EXISTS events (
  run_id TEXT NOT NULL REFERENCES runs(run_id),
  seq INTEGER NOT NULL CHECK (seq >= 1),
  ts TEXT NOT NULL,
  type TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  PRIMARY KEY (run_id, seq)
);

CREATE TABLE IF NOT EXISTS artifacts (
  artifact_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES runs(run_id),
  kind TEXT NOT NULL,
  filename TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
  content_base64 TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_artifacts_run_id ON artifacts(run_id);

CREATE TABLE IF NOT EXISTS operations (
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

CREATE INDEX IF NOT EXISTS idx_operations_run_status ON operations(run_id, status);
"""

MIGRATION_0002 = """
CREATE TABLE IF NOT EXISTS tasks (
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

CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at);
"""

MIGRATIONS = [
    ("0001_initial_schema", MIGRATION_0001),
    ("0002_tasks_table", MIGRATION_0002),
]


def apply_migrations(conn: Any) -> list[str]:
    """Apply pending schema migrations to libSQL / SQLite connection idempotently."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        "  version TEXT PRIMARY KEY,"
        "  applied_at TEXT NOT NULL"
        ");"
    )
    conn.commit()

    cur = conn.execute("SELECT version FROM schema_migrations")
    applied = {row[0] for row in cur.fetchall()}

    newly_applied = []
    for version, sql in MIGRATIONS:
        if version not in applied:
            logger.info("Applying migration %s", version)
            for statement in sql.strip().split(";"):
                stmt = statement.strip()
                if stmt:
                    conn.execute(stmt)
            import datetime

            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            conn.execute(
                "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                (version, now),
            )
            conn.commit()
            newly_applied.append(version)

    return newly_applied
