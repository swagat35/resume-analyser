"""
Centralized application configuration.
All secrets/config come from environment variables (.env locally,
real environment variables in production) — never hardcoded.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    # Auth
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24 hours

    # LLM
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    # DB
    database_url: str = "sqlite:///./resume_analyzer.db"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # App
    environment: str = "development"
    max_upload_size_mb: int = 2
    allowed_origins: str = "http://localhost:8501"
    rate_limit_per_minute: int = 10
    log_level: str = "INFO"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    # Cached so we don't re-read/parse env on every request.
    return Settings()
