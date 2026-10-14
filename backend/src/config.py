from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Cloudflare D1 Worker bridge
    repomedic_db_worker_url: str = "https://repo-medic-api.souvik-dev112.workers.dev"
    db_bridge_token: str = ""

    # Nebius Token Factory inference & sandbox
    nebius_api_key: str = ""
    nebius_project_id: str = ""
    nebius_sandbox_image: str = "python:3.12-slim"
    token_factory_base_url: str = "https://api.tokenfactory.us-central1.nebius.com/v1/"
    token_factory_model: str = "nvidia/nemotron-3-super-120b-a12b"

    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

settings = Settings()
