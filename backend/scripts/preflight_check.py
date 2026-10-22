#!/usr/bin/env python3
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.preflight import (  # noqa: E402
    EXPECTED_TABLES,
    run_preflight,
    verify_schema_tables,
    verify_wrangler_config,
)


def run_command(cmd: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except Exception as e:
        return 1, "", str(e)


def main() -> int:
    parser = argparse.ArgumentParser(description="Preflight verification for Cloudflare D1 deployment")
    parser.add_argument(
        "--wrangler-path",
        type=Path,
        default=Path(__file__).resolve().parent.parent.parent / "db-worker" / "wrangler.toml",
        help="Path to db-worker wrangler.toml",
    )
    parser.add_argument(
        "--remote",
        action="store_true",
        help="Execute live remote checks via wrangler CLI",
    )
    args = parser.parse_args()

    print("=== RepoMedic K3 Preflight Verification ===")
    print(f"Inspecting wrangler configuration: {args.wrangler_path}")

    config_res = verify_wrangler_config(args.wrangler_path)
    for check in config_res.checks:
        status_str = "PASS" if check.get("passed") else "FAIL"
        print(f"  [{status_str}] {check.get('name')}: actual='{check.get('actual')}'")

    if not config_res.passed:
        print("\nPreflight configuration errors detected:")
        for err in config_res.errors:
            print(f"  - {err}")

    if not args.remote:
        print("\nOffline preflight complete. Use --remote to execute live Cloudflare CLI checks.")
        return 0 if config_res.passed else 1

    print("\nExecuting live remote Cloudflare preflight checks...")
    if not shutil.which("npx"):
        print("  [FAIL] npx executable not found in PATH")
        return 1

    worker_dir = args.wrangler_path.parent if args.wrangler_path.is_file() else (
        Path(__file__).resolve().parent.parent.parent / "db-worker"
    )

    # 1. Whoami check
    code, out, err = run_command(["npx", "wrangler", "whoami"], cwd=worker_dir)
    if code == 0:
        print(f"  [PASS] wrangler whoami: {out.splitlines()[0] if out else 'ok'}")
    else:
        print(f"  [FAIL] wrangler whoami failed: {err}")
        return 1

    # 2. Database info check
    code, out, err = run_command(
        ["npx", "wrangler", "d1", "info", "repomedic-db", "--config", str(args.wrangler_path)],
        cwd=worker_dir,
    )
    if code == 0:
        print("  [PASS] wrangler d1 info repomedic-db confirmed")
    else:
        print(f"  [FAIL] wrangler d1 info repomedic-db failed: {err}")
        return 1

    # 3. Schema inspection check
    sql = "SELECT name FROM sqlite_master WHERE type='table';"
    code, out, err = run_command(
        [
            "npx",
            "wrangler",
            "d1",
            "execute",
            "repomedic-db",
            "--remote",
            "--config",
            str(args.wrangler_path),
            "--command",
            sql,
            "--json",
        ],
        cwd=worker_dir,
    )
    if code == 0:
        try:
            data = json.loads(out)
            results = data[0].get("results", []) if isinstance(data, list) and data else []
            table_names = [
                str(r["name"]) for r in results if isinstance(r, dict) and r.get("name") is not None
            ]
            schema_res = verify_schema_tables(table_names)
            for check in schema_res.checks:
                status_str = "PASS" if check.get("passed") else "FAIL"
                print(f"  [{status_str}] table: {check.get('table')}")
            if not schema_res.passed:
                for err_msg in schema_res.errors:
                    print(f"  - {err_msg}")
                return 1
        except Exception as parse_err:
            print(f"  [FAIL] Failed to parse schema results: {parse_err}")
            return 1
    else:
        print(f"  [FAIL] Remote schema execution failed: {err}")
        return 1

    print("\nAll preflight verification checks passed successfully!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
