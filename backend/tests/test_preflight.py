from pathlib import Path

from src.preflight import (
    run_preflight,
    verify_live_providers,
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


def test_verify_live_providers_all_valid() -> None:
    env = {
        "TOKEN_FACTORY_API_KEY": "tf-secret-123",
        "TOKEN_FACTORY_BASE_URL": "https://api.tokenfactory.us-central1.nebius.com/v1/",
        "TOKEN_FACTORY_MODEL": "nvidia/nemotron-3-super-120b-a12b",
        "NEBIUS_API_KEY": "neb-secret-456",
        "NEBIUS_PROJECT_ID": "proj-789",
        "NEBIUS_SANDBOX_IMAGE": "python:3.12-bookworm",
    }
    res = verify_live_providers(env=env)
    assert res.passed is True
    assert len(res.errors) == 0


def test_verify_live_providers_missing_credentials_fails() -> None:
    env = {
        "TOKEN_FACTORY_API_KEY": "",
        "NEBIUS_API_KEY": "",
        "NEBIUS_PROJECT_ID": "",
    }
    res = verify_live_providers(env=env)
    assert res.passed is False
    assert any("TOKEN_FACTORY_API_KEY" in err for err in res.errors)
    assert any("NEBIUS_API_KEY" in err for err in res.errors)
    assert any("NEBIUS_PROJECT_ID" in err for err in res.errors)


def test_verify_live_providers_repository_access_with_sha() -> None:
    """covers: AC-3 - Confirms preflight verifies public repository access with full commit SHA."""
    res = verify_live_providers(
        repository_url="https://github.com/SGOD-pro/repo-medic.git",
        commit_sha="453a0b6c6b125177504cdd941902b8d48266ed1c",
    )
    assert res.passed is True
    repo_check = next((c for c in res.checks if c.get("name") == "repository_access"), None)
    assert repo_check is not None
    assert repo_check.get("passed") is True


def test_verify_live_providers_spending_limits_zero_or_negative() -> None:
    """covers: AC-10 - Confirms preflight rejects zero or negative budget limits."""
    res_zero = verify_live_providers(max_run_usd=0.0)
    assert res_zero.passed is False
    assert any("spending_and_time_limits" in c.get("name", "") and not c.get("passed") for c in res_zero.checks)

    res_neg = verify_live_providers(total_budget_usd=-5.0)
    assert res_neg.passed is False


def test_verify_live_providers_contree_class_missing(monkeypatch) -> None:
    """covers: AC-2 - Confirms preflight flags missing Contree class even if package is importable."""
    import types
    fake_mod = types.ModuleType("contree_sdk")
    monkeypatch.setattr("importlib.import_module", lambda name: fake_mod if name == "contree_sdk" else __import__(name))

    res = verify_live_providers()
    assert res.passed is False
    assert any("Contree class is not available" in err for err in res.errors)
