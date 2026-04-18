from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openrouter_api_key: str = "sk-or-missing"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    data_service_url: str = "http://data-service:8001"
    redis_url: str = "redis://redis:6379/0"
    cache_ttl_seconds: int = 604800
    llm_timeout_seconds: int = 30
    llm_daily_budget_usd: float = 100.0
    log_level: str = "INFO"
    prompt_version: str = "v1"
    environment: str = "dev"
    dry_run: bool = False


settings = Settings()
