-- Migration: 0003_active_run_constraint_and_idempotency.sql
-- RepoMedic Cloudflare D1 Active Run Constraint and Idempotency Table

CREATE UNIQUE INDEX IF NOT EXISTS idx_active_run_per_task ON runs(task_id) WHERE state IN ('queued', 'running');

CREATE TABLE IF NOT EXISTS idempotency_keys (
  key TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES runs(run_id),
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_idempotency_run_id ON idempotency_keys(run_id);
