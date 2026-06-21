from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Application
    app_name: str = "Prompt Platform"
    debug: bool = False
    api_prefix: str = "/api/v1"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/prompt_platform"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # JWT
    jwt_secret_key: str = "change-me-in-production-use-a-strong-random-key"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # LLM Providers
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    anthropic_api_key: str | None = None
    deepseek_api_key: str | None = None
    deepseek_base_url: str = "https://api.deepseek.com/v1"

    # Cache
    cache_ttl_seconds: int = 3600

    # Rate Limit
    llm_max_concurrent: int = 10

    # CORS
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    @property
    def database_url_sync(self) -> str:
        return self.database_url.replace("+asyncpg", "")


settings = Settings()
