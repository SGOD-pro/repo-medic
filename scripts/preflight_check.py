#!/usr/bin/env python3
"""Preflight inspection CLI for RepoMedic.

Validates cloud configurations, database schema, and live provider connectivity.
Run with --live-providers to inspect Token Factory and ConTree settings.
"""

import argparse
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
    _backend_env = Path(__file__).resolve().parents[1] / "backend" / ".env"
    if _backend_env.is_file():
        load_dotenv(_backend_env)
except ImportError:
    pass

# Add backend directory to python path
repo_root = Path(__file__).resolve().parents[1]
backend_dir = repo_root / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# Also support execution from within backend directory
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from src.preflight import run_preflight, verify_live_providers  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="RepoMedic preflight inspection")
    parser.add_argument(
        "--live-providers",
        action="store_true",
        help="Inspect live provider credentials, URLs, models, and contree-sdk",
    )
    parser.add_argument(
        "--wrangler-path",
        type=Path,
        default=None,
        help="Path to db-worker wrangler.toml",
    )
    args = parser.parse_args()

    print("=== RepoMedic Preflight Inspection ===")
    exit_code = 0

    if args.live_providers:
        print("\n--- Live Provider Inspection ---")
        result = verify_live_providers()
        for check in result.checks:
            status = "PASS" if check["passed"] else "FAIL"
            print(f"[{status}] {check['name']}: {check}")
        if not result.passed:
            print("\nErrors encountered:")
            for err in result.errors:
                print(f"  * {err}")
            exit_code = 1
        else:
            print("\nAll live provider preflight checks passed.")
        return exit_code

    print("\n--- Database Target and Schema Preflight ---")
    result = run_preflight(wrangler_path=args.wrangler_path)
    for check in result.checks:
        status = "PASS" if check["passed"] else "FAIL"
        print(f"[{status}] {check.get('name') or check.get('table')}: {check}")
    if not result.passed:
        print("\nErrors encountered:")
        for err in result.errors:
            print(f"  * {err}")
        exit_code = 1
    else:
        print("\nAll target and schema preflight checks passed.")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
