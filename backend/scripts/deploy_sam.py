import subprocess
import sys

# Non-secret infrastructure parameters for deployment.
# Secret parameters (Turso and Nebius credentials) are maintained in CloudFormation
# state or referenced via AWS Systems Manager / Secrets Manager, rather than passed
# as cleartext command-line arguments to avoid exposure in process tables or shell logs.
overrides = [
    'Environment="production"',
    'AppOrigin="https://repo-medic-gamma.vercel.app"',
    'NebiusProjectId="aiproject-e00dze5s6fmv4cemqz"',
    'RepairMode="live"',
    'UseRealEngine="true"',
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
