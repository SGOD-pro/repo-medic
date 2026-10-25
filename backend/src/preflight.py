import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


ZERO_UUID = "00000000-0000-0000-0000-000000000000"
UUID_REGEX = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

EXPECTED_TABLES = [
    "runs",
    "events",
    "artifacts",
    "operations",
    "tasks",
]


@dataclass
class PreflightResult:
    passed: bool
    checks: List[Dict[str, Any]]
    errors: List[str]


def verify_wrangler_config(config_path: Path) -> PreflightResult:
    """Validate db worker wrangler configuration for database binding and id."""
    checks: List[Dict[str, Any]] = []
    errors: List[str] = []

    if not config_path.is_file():
        errors.append(f"Wrangler config not found at {config_path}")
        return PreflightResult(passed=False, checks=checks, errors=errors)

    try:
        with open(config_path, "rb") as f:
            data = tomllib.load(f)
    except Exception as e:
        errors.append(f"Failed to parse wrangler config: {e}")
        return PreflightResult(passed=False, checks=checks, errors=errors)

    d1_list = data.get("d1_databases", [])
    if not isinstance(d1_list, list) or len(d1_list) == 0:
        errors.append("No d1_databases entries defined in wrangler config")
        return PreflightResult(passed=False, checks=checks, errors=errors)

    db_entry = d1_list[0]
    binding = db_entry.get("binding", "")
    db_name = db_entry.get("database_name", "")
    db_id = db_entry.get("database_id", "")

    # Check 1: Binding name
    binding_ok = binding == "DB"
    checks.append({
        "name": "binding_name",
        "expected": "DB",
        "actual": binding,
        "passed": binding_ok,
    })
    if not binding_ok:
        errors.append(f"Binding name must be 'DB', found '{binding}'")

    # Check 2: Database name
    name_ok = db_name == "repomedic-db"
    checks.append({
        "name": "database_name",
        "expected": "repomedic-db",
        "actual": db_name,
        "passed": name_ok,
    })
    if not name_ok:
        errors.append(f"Database name must be 'repomedic-db', found '{db_name}'")

    # Check 3: Database ID format and non placeholder
    is_valid_uuid = bool(UUID_REGEX.match(db_id))
    is_not_zero = db_id.lower() != ZERO_UUID
    db_id_ok = is_valid_uuid and is_not_zero
    checks.append({
        "name": "database_id",
        "actual": db_id,
        "is_valid_uuid": is_valid_uuid,
        "is_not_placeholder": is_not_zero,
        "passed": db_id_ok,
    })
    if not is_valid_uuid:
        errors.append(f"Database ID '{db_id}' is not a valid UUID format")
    elif not is_not_zero:
        errors.append("Database ID is still configured with placeholder zero UUID")

    passed = len(errors) == 0
    return PreflightResult(passed=passed, checks=checks, errors=errors)


def verify_schema_tables(table_names: List[str]) -> PreflightResult:
    """Verify that required tables exist in database schema."""
    checks: List[Dict[str, Any]] = []
    errors: List[str] = []

    existing = set(table_names)
    for expected in EXPECTED_TABLES:
        ok = expected in existing
        checks.append({
            "table": expected,
            "present": ok,
            "passed": ok,
        })
        if not ok:
            errors.append(f"Required table '{expected}' is missing from schema")

    passed = len(errors) == 0
    return PreflightResult(passed=passed, checks=checks, errors=errors)


def run_preflight(
    wrangler_path: Optional[Path] = None,
    table_names: Optional[List[str]] = None,
) -> PreflightResult:
    """Run full preflight target and schema verification."""
    if wrangler_path is None:
        wrangler_path = Path(__file__).resolve().parents[2] / "db-worker" / "wrangler.toml"

    all_checks: List[Dict[str, Any]] = []
    all_errors: List[str] = []

    config_res = verify_wrangler_config(wrangler_path)
    all_checks.extend(config_res.checks)
    all_errors.extend(config_res.errors)

    if table_names is not None:
        schema_res = verify_schema_tables(table_names)
        all_checks.extend(schema_res.checks)
        all_errors.extend(schema_res.errors)

    passed = len(all_errors) == 0
    return PreflightResult(passed=passed, checks=all_checks, errors=all_errors)


def verify_live_providers(
    env: Optional[Dict[str, str]] = None,
    repository_url: Optional[str] = None,
    commit_sha: Optional[str] = None,
    max_run_usd: Optional[float] = None,
    total_budget_usd: Optional[float] = None,
    timeout_seconds: Optional[int] = None,
) -> PreflightResult:
    """Validate live provider credentials, URLs, package availability, repository access, and spend limits."""
    import importlib
    import os
    import subprocess

    source_env: Dict[str, str] = dict(os.environ) if env is None else dict(env)
    if env is None:
        try:
            from dotenv import load_dotenv
            backend_env_file = Path(__file__).resolve().parent.parent / ".env"
            if backend_env_file.is_file():
                load_dotenv(backend_env_file)
                source_env.update(os.environ)
        except Exception:
            pass
        try:
            from src.config import settings
            settings_map = {
                "TOKEN_FACTORY_API_KEY": settings.token_factory_api_key,
                "TOKEN_FACTORY_BASE_URL": settings.token_factory_base_url,
                "TOKEN_FACTORY_MODEL": settings.token_factory_model,
                "NEBIUS_API_KEY": settings.nebius_api_key,
                "NEBIUS_PROJECT_ID": settings.nebius_project_id,
                "NEBIUS_SANDBOX_IMAGE": settings.nebius_sandbox_image,
            }
            for k, v in settings_map.items():
                if v and k not in source_env:
                    source_env[k] = v
        except Exception:
            pass
    checks: List[Dict[str, Any]] = []
    errors: List[str] = []

    # 1. Token Factory API Key
    tf_key = (source_env.get("TOKEN_FACTORY_API_KEY") or source_env.get("NEBIUS_API_KEY") or "").strip()
    tf_key_ok = bool(tf_key and not tf_key.startswith("placeholder"))
    checks.append({
        "name": "token_factory_api_key",
        "configured": tf_key_ok,
        "passed": tf_key_ok,
    })
    if not tf_key_ok:
        errors.append("TOKEN_FACTORY_API_KEY (or NEBIUS_API_KEY) is missing or unconfigured")

    # 2. Token Factory Base URL
    default_base_url = "https://api.tokenfactory.us-central1.nebius.com/v1/"
    base_url = (source_env.get("TOKEN_FACTORY_BASE_URL") or default_base_url).strip()
    url_ok = base_url.startswith("http://") or base_url.startswith("https://")
    checks.append({
        "name": "token_factory_base_url",
        "actual": base_url,
        "passed": url_ok,
    })
    if not url_ok:
        errors.append(f"TOKEN_FACTORY_BASE_URL must be a valid HTTP or HTTPS URL, found '{base_url}'")

    # 3. Token Factory Model
    model_name = (source_env.get("TOKEN_FACTORY_MODEL") or "nvidia/nemotron-3-super-120b-a12b").strip()
    model_ok = bool(model_name)
    checks.append({
        "name": "token_factory_model",
        "actual": model_name,
        "passed": model_ok,
    })
    if not model_ok:
        errors.append("TOKEN_FACTORY_MODEL is not specified")

    # 4. Nebius API Key for ConTree SDK
    neb_key = (source_env.get("NEBIUS_API_KEY") or "").strip()
    neb_key_ok = bool(neb_key and not neb_key.startswith("placeholder"))
    checks.append({
        "name": "nebius_api_key",
        "configured": neb_key_ok,
        "passed": neb_key_ok,
    })
    if not neb_key_ok:
        errors.append("NEBIUS_API_KEY is missing or unconfigured")

    # 5. Nebius Project ID
    proj_id = (source_env.get("NEBIUS_PROJECT_ID") or source_env.get("TOKEN_FACTORY_SANDBOX_PROJECT_ID") or "").strip()
    proj_id_ok = bool(proj_id and not proj_id.startswith("placeholder"))
    checks.append({
        "name": "nebius_project_id",
        "configured": proj_id_ok,
        "passed": proj_id_ok,
    })
    if not proj_id_ok:
        errors.append("NEBIUS_PROJECT_ID is missing or unconfigured")

    # 6. Nebius Sandbox Image
    image_name = (source_env.get("NEBIUS_SANDBOX_IMAGE") or "python:3.12-bookworm").strip()
    image_ok = bool(image_name)
    checks.append({
        "name": "nebius_sandbox_image",
        "actual": image_name,
        "passed": image_ok,
    })
    if not image_ok:
        errors.append("NEBIUS_SANDBOX_IMAGE is empty")

    # 7. contree-sdk package import and operation check
    contree_installed = False
    contree_ops_ok = False
    try:
        mod = importlib.import_module("contree_sdk")
        contree_installed = True
        contree_ops_ok = hasattr(mod, "Contree")
    except ImportError:
        contree_installed = False

    checks.append({
        "name": "contree_sdk_installed",
        "installed": contree_installed,
        "operations_available": contree_ops_ok,
        "passed": contree_installed and contree_ops_ok,
    })
    if not contree_installed:
        errors.append("contree-sdk package is not installed in the python environment")
    elif not contree_ops_ok:
        errors.append("contree-sdk Contree class is not available")

    # 8. Spending and time bounds verification
    from src.config import settings
    raw_max_run = source_env.get("REPOMEDIC_MAX_RUN_USD")
    default_max_run = getattr(settings, "repomedic_max_run_usd", 2.0)
    max_run_cap = max_run_usd if max_run_usd is not None else (float(raw_max_run) if raw_max_run else default_max_run)

    raw_total_budget = source_env.get("REPOMEDIC_TOTAL_BUDGET_USD")
    default_total = getattr(settings, "repomedic_total_budget_usd", 25.0)
    total_budget_cap = total_budget_usd if total_budget_usd is not None else (
        float(raw_total_budget) if raw_total_budget else default_total
    )
    timeout_cap = int(timeout_seconds if timeout_seconds is not None else 600)

    limits_ok = (0 < max_run_cap <= 2.0) and (0 < total_budget_cap <= 25.0) and (0 < timeout_cap <= 600)
    checks.append({
        "name": "spending_and_time_limits",
        "max_run_usd": max_run_cap,
        "total_budget_usd": total_budget_cap,
        "timeout_seconds": timeout_cap,
        "passed": limits_ok,
    })
    if max_run_cap <= 0 or max_run_cap > 2.0:
        errors.append(f"REPOMEDIC_MAX_RUN_USD ({max_run_cap}) must be positive and not exceed 2.00 USD")
    if total_budget_cap <= 0 or total_budget_cap > 25.0:
        errors.append(f"REPOMEDIC_TOTAL_BUDGET_USD ({total_budget_cap}) must be positive and not exceed 25.00 USD")
    if timeout_cap <= 0 or timeout_cap > 600:
        errors.append(f"timeout_seconds ({timeout_cap}) must be positive and not exceed 600 seconds")

    # 9. Repository access preflight check
    if repository_url:
        repo_accessible = False
        repo_err = ""
        try:
            cmd = ["git", "ls-remote", repository_url]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if res.returncode == 0:
                if commit_sha:
                    sha_match = (commit_sha in res.stdout) or (commit_sha[:7] in res.stdout)
                    repo_accessible = sha_match or len(res.stdout.strip()) > 0
                else:
                    repo_accessible = len(res.stdout.strip()) > 0
            else:
                repo_err = res.stderr.strip() or f"exit code {res.returncode}"
        except Exception as exc:
            repo_err = str(exc)

        checks.append({
            "name": "repository_access",
            "repository_url": repository_url,
            "commit_sha": commit_sha,
            "accessible": repo_accessible,
            "passed": repo_accessible,
        })
        if not repo_accessible:
            errors.append(f"Repository {repository_url} is not accessible: {repo_err}")

    passed = len(errors) == 0
    return PreflightResult(passed=passed, checks=checks, errors=errors)
