from pathlib import Path

from src.preflight import (
    run_preflight,
    verify_schema_tables,
    verify_wrangler_config,
)


def test_verify_wrangler_config_valid(tmp_path: Path) -> None:
    config_file = tmp_path / "wrangler.toml"
    config_file.write_text("""
name = "repomedic-db-worker"
main = "src/index.ts"

[[d1_databases]]
binding = "DB"
database_name = "repomedic-db"
database_id = "12345678-abcd-1234-abcd-123456789abc"
""", encoding="utf-8")

    res = verify_wrangler_config(config_file)
    assert res.passed is True
    assert len(res.errors) == 0


def test_verify_wrangler_config_zero_uuid_fails(tmp_path: Path) -> None:
    config_file = tmp_path / "wrangler.toml"
    config_file.write_text("""
name = "repomedic-db-worker"

[[d1_databases]]
binding = "DB"
database_name = "repomedic-db"
database_id = "00000000-0000-0000-0000-000000000000"
""", encoding="utf-8")

    res = verify_wrangler_config(config_file)
    assert res.passed is False
    assert any("placeholder zero UUID" in e for e in res.errors)


def test_verify_wrangler_config_invalid_binding_fails(tmp_path: Path) -> None:
    config_file = tmp_path / "wrangler.toml"
    config_file.write_text("""
name = "repomedic-db-worker"

[[d1_databases]]
binding = "WRONG_DB"
database_name = "repomedic-db"
database_id = "12345678-abcd-1234-abcd-123456789abc"
""", encoding="utf-8")

    res = verify_wrangler_config(config_file)
    assert res.passed is False
    assert any("Binding name must be 'DB'" in e for e in res.errors)


def test_verify_schema_tables_complete() -> None:
    tables = ["runs", "events", "artifacts", "operations", "tasks", "d1_migrations"]
    res = verify_schema_tables(tables)
    assert res.passed is True
    assert len(res.errors) == 0


def test_verify_schema_tables_missing_tasks() -> None:
    tables = ["runs", "events", "artifacts", "operations"]
    res = verify_schema_tables(tables)
    assert res.passed is False
    assert any("tasks" in e for e in res.errors)


def test_run_preflight_end_to_end(tmp_path: Path) -> None:
    config_file = tmp_path / "wrangler.toml"
    config_file.write_text("""
name = "repomedic-db-worker"

[[d1_databases]]
binding = "DB"
database_name = "repomedic-db"
database_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
""", encoding="utf-8")

    tables = ["runs", "events", "artifacts", "operations", "tasks"]
    res = run_preflight(wrangler_path=config_file, table_names=tables)
    assert res.passed is True
    assert len(res.errors) == 0


def test_run_preflight_default_path_resolves() -> None:
    # Verifies default wrangler path resolves dynamically to repo db-worker/wrangler.toml
    res = run_preflight()
    # It will detect binding DB and database repomedic-db from wrangler.toml
    binding_check = next((c for c in res.checks if c.get("name") == "binding_name"), None)
    assert binding_check is not None
    assert binding_check.get("passed") is True
