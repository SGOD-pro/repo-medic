-- Migration: 0001_initial_schema.sql
-- RepoMedic Cloudflare D1 Initial Schema

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
