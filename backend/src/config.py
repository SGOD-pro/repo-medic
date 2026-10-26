from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Execution mode & frontend integration
    repomedic_mode: str = "offline"
    repomedic_app_origin: str = "http://localhost:3000"
    repomedic_env: str = "development"
    environment: str = "development"

    # Cloudflare D1 Worker bridge (legacy/bridge fallback)
    repomedic_db_worker_url: str = "http://127.0.0.1:8787"
    repomedic_db_worker_token: str = "local-bridge-token"
    db_bridge_token: str = "local-bridge-token"

    # Turso / libSQL Persistence
    turso_database_url: str = ""
    turso_auth_token: str = ""
    repomedic_database_url: str = ""
    repomedic_database_auth_token: str = ""
    db_url: str = ""
    api_key: str = ""
    repomedic_storage_backend: str = "turso"

    # Budgets, deadlines & safety limits
    repomedic_max_run_usd: float = 2.0
    repomedic_total_budget_usd: float = 25.0
    repomedic_max_model_calls: int = 1
    repomedic_max_output_tokens: int = 2048
    repomedic_run_timeout_seconds: int = 600
    repomedic_max_artifact_bytes: int = 1048576

    # Worker queue & execution
    repomedic_worker_enabled: bool = True
    repomedic_worker_poll_interval_seconds: float = 1.0
    repomedic_use_real_engine: bool = False
    repomedic_sync_fixtures: bool = True
    repomedic_acceptance_prefix: str = ""

    # Nebius Token Factory inference & sandbox
    token_factory_api_key: str = ""
    token_factory_base_url: str = "https://api.tokenfactory.us-central1.nebius.com/v1/"
    token_factory_model: str = "nvidia/nemotron-3-super-120b-a12b"
    token_factory_sandbox_base_url: str = ""
    token_factory_sandbox_token: str = ""
    token_factory_sandbox_project_id: str = ""
    token_factory_sandbox_image_id: str = ""

    # Legacy / provider aliases used in adapters and scripts
    nebius_api_key: str = ""
    nebius_project_id: str = ""
    nebius_sandbox_image: str = "python:3.12-bookworm"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
