import subprocess
import sys
from dotenv import dotenv_values

vals = dotenv_values(".env")
turso_url = vals.get("TURSO_DATABASE_URL", "")
turso_token = vals.get("TURSO_AUTH_TOKEN", "")
nebius_key = vals.get("NEBIUS_API_KEY", "")

overrides = [
    'Environment="production"',
    'AppOrigin="https://repo-medic-gamma.vercel.app"',
    'NebiusProjectId="aiproject-e00dze5s6fmv4cemqz"',
    'RepairMode="live"',
    'UseRealEngine="true"',
    f'TursoDatabaseUrl="{turso_url}"',
    f'TursoAuthToken="{turso_token}"',
    f'NebiusApiKey="{nebius_key}"',
]

cmd = [
    "sam",
    "deploy",
    "--no-confirm-changeset",
    "--parameter-overrides",
    " ".join(overrides),
]

res = subprocess.run(cmd)
sys.exit(res.returncode)
