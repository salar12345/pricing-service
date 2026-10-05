from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "postgresql+asyncpg://pricing:pricing@localhost:5432/pricing"
    redis_url: str = "redis://localhost:6379/0"
    log_level: str = "info"


@lru_cache
def get_settings() -> Settings:
    return Settings()
