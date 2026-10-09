import os
import json

os.makedirs('backend/src/engine', exist_ok=True)
os.makedirs('backend/src/storage', exist_ok=True)

fake_engine_py = """\
from backend.src.contracts import RepairRequest, TaskRecipe, HostPorts, RepairResult

async def repair(request: RepairRequest, recipe: TaskRecipe, host: HostPorts) -> RepairResult:
    await host.emit("status", {"message": "Starting fake repair"})
    await host.reserve("model:1", 0.05)
    if await host.cancelled():
        return RepairResult(state="cancelled", reason="User cancelled")
    await host.settle("model:1", 0.05)
    return RepairResult(state="succeeded", reason="Fake success")
"""

fake_host_py = """\
from backend.src.contracts import HostPorts

class FakeHost:
    def __init__(self):
        self.events = []
        self.artifacts = []
        self.reservations = {}
        self.settlements = {}
        self.is_cancelled = False
    
    async def emit(self, event_type: str, payload: dict) -> None:
        self.events.append({"type": event_type, "payload": payload})
        
    async def save_artifact(self, kind: str, filename: str, content: bytes) -> str:
        self.artifacts.append({"kind": kind, "filename": filename})
        return f"fake_path/{filename}"
        
    async def reserve(self, operation_id: str, estimated_usd: float) -> bool:
        self.reservations[operation_id] = estimated_usd
        return True
        
    async def settle(self, operation_id: str, actual_or_estimated_usd: float) -> None:
        self.settlements[operation_id] = actual_or_estimated_usd
        
    async def cancelled(self) -> bool:
        return self.is_cancelled
        
    async def record_provider_ref(self, operation_id: str, provider_ref: str) -> None:
        pass
"""

with open('backend/src/engine/fake_engine.py', 'w') as f:
    f.write(fake_engine_py)
    
with open('backend/src/storage/fake_host.py', 'w') as f:
    f.write(fake_host_py)

config_py = """\
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    repomedic_mode: str = "offline"
    repomedic_app_origin: str = "http://localhost:3000"
    repomedic_db_worker_url: str = "http://localhost:8787"
    repomedic_db_worker_token: str = "dummy_secret"
    db_bridge_token: str = "dummy_secret"
    repomedic_total_budget_usd: float = 25.0
    repomedic_max_model_calls: int = 1
    repomedic_max_output_tokens: int = 2048
    repomedic_run_timeout_seconds: int = 600
    repomedic_max_artifact_bytes: int = 1048576

    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

settings = Settings()
"""

with open('backend/src/config.py', 'w') as f:
    f.write(config_py)

env_example = """\
REPOMEDIC_MODE=offline
REPOMEDIC_APP_ORIGIN=http://localhost:3000
REPOMEDIC_DB_WORKER_URL=http://localhost:8787
REPOMEDIC_DB_WORKER_TOKEN=dummy_secret
DB_BRIDGE_TOKEN=dummy_secret
REPOMEDIC_MAX_RUN_USD=2.0
REPOMEDIC_TOTAL_BUDGET_USD=25
REPOMEDIC_MAX_MODEL_CALLS=1
REPOMEDIC_MAX_OUTPUT_TOKENS=2048
REPOMEDIC_RUN_TIMEOUT_SECONDS=600
REPOMEDIC_MAX_ARTIFACT_BYTES=1048576
TOKEN_FACTORY_API_KEY=
TOKEN_FACTORY_BASE_URL=
TOKEN_FACTORY_MODEL=
TOKEN_FACTORY_SANDBOX_BASE_URL=
TOKEN_FACTORY_SANDBOX_TOKEN=
TOKEN_FACTORY_SANDBOX_PROJECT_ID=
TOKEN_FACTORY_SANDBOX_IMAGE_ID=
"""

with open('.env.example', 'w') as f:
    f.write(env_example)

