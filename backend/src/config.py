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
