from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    repomedic_mode: str = "offline"
    repomedic_app_origin: str = "http://localhost:3000"
    repomedic_db_worker_url: str = "https://repo-medic-api.souvik-dev112.workers.dev"
    repo_medic_api_key: str = ""
    db_bridge_token: str = ""
    repomedic_max_run_usd: float = 2.0
    repomedic_total_budget_usd: float = 25.0
    repomedic_max_model_calls: int = 1
    repomedic_max_output_tokens: int = 2048
    repomedic_run_timeout_seconds: int = 600
    repomedic_max_artifact_bytes: int = 1048576
    token_factory_api_key: str = ""
    token_factory_base_url: str = ""
    token_factory_model: str = ""
    token_factory_sandbox_base_url: str = ""
    token_factory_sandbox_token: str = ""
    token_factory_sandbox_project_id: str = ""
    token_factory_sandbox_image_id: str = ""

    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

settings = Settings()
