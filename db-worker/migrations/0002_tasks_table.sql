-- Migration: 0002_tasks_table.sql
-- RepoMedic Cloudflare D1 Tasks Table

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
