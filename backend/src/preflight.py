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


def verify_live_providers(env: Optional[Dict[str, str]] = None) -> PreflightResult:
    """Validate live provider credentials, URLs, and package availability."""
    import importlib
    import os

    source_env = os.environ if env is None else env
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

    # 7. contree-sdk package import check
    contree_installed = False
    try:
        importlib.import_module("contree_sdk")
        contree_installed = True
    except ImportError:
        contree_installed = False

    checks.append({
        "name": "contree_sdk_installed",
        "installed": contree_installed,
        "passed": contree_installed,
    })
    if not contree_installed:
        errors.append("contree-sdk package is not installed in the python environment")

    passed = len(errors) == 0
    return PreflightResult(passed=passed, checks=checks, errors=errors)
