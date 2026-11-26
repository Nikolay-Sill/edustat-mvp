"""Настройки приложения: читаются из переменных окружения с префиксом EDUSTAT_ или из backend/.env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="EDUSTAT_", env_file=".env", extra="ignore")

    # Значения по умолчанию совпадают с docker-compose.yml — проект запускается без .env
    database_url: str = "postgresql+psycopg://edustat:edustat@localhost:55432/edustat"
    test_database_url: str = "postgresql+psycopg://edustat:edustat@localhost:55432/edustat_test"
    log_level: str = "INFO"

    # Префикс API из раздела servers в edustat-openapi.yaml
    api_prefix: str = "/api/v1"


@lru_cache
def get_settings() -> Settings:
    return Settings()
