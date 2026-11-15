"""Application settings loaded from environment variables and an optional `.env` file.

All variables use the ``EXPSYS_`` prefix, e.g. ``EXPSYS_LOG_LEVEL=DEBUG``.
Real environment variables take precedence over values in `.env`.
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

AppEnv = Literal["dev", "test"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class Settings(BaseSettings):
    """Global, typed application settings.

    Values are validated on construction: an unknown ``app_env`` or ``log_level``
    raises ``pydantic.ValidationError`` instead of being silently accepted.
    """

    model_config = SettingsConfigDict(
        env_prefix="EXPSYS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: AppEnv = "dev"
    log_level: LogLevel = "INFO"

    # TODO(later): LLM provider settings (provider-agnostic: provider name, model,
    # base URL, API key as SecretStr) — added together with the LLM provider layer.
    # TODO(later): orchestrator max_iterations — added together with the orchestrator.


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings instance (created once, then cached)."""
    return Settings()
