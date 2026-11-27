"""Application settings loaded from environment variables and an optional `.env` file.

Application variables use the ``EXPSYS_`` prefix, e.g. ``EXPSYS_LOG_LEVEL=DEBUG``.
Provider variables keep their conventional names (``OPENROUTER_API_KEY``,
``DEFAULT_MODEL``, ``SCIENTIST_MODEL``, ...).
Real environment variables take precedence over values in `.env`.

Model names are never hard-coded: they come only from these settings / `.env`.
"""

from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

AppEnv = Literal["dev", "test"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
StructuredMode = Literal["auto", "json_schema", "text"]
AgentName = Literal["scientist", "experiment", "runner", "analyst"]
AGENT_NAMES: tuple[AgentName, ...] = ("scientist", "experiment", "runner", "analyst")


class ConfigError(ValueError):
    """A required setting is missing for the requested mode."""


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
        populate_by_name=True,
    )

    app_env: AppEnv = "dev"
    log_level: LogLevel = "INFO"

    # --- orchestrator ----------------------------------------------------------------------
    max_iterations: int = Field(default=5, gt=0)
    max_llm_calls: int = Field(default=40, gt=0)  # agent calls per run (each <= max attempts)
    require_approval: bool = False
    runs_dir: Path = Path("runs")
    registry_path: Path = Path("configs/devices/simulation.yaml")
    scenarios_dir: Path = Path("configs/scenarios")

    # --- LLM provider (OpenRouter, OpenAI-compatible API) ---------------------------------
    openrouter_api_key: SecretStr | None = Field(
        default=None, validation_alias="OPENROUTER_API_KEY"
    )
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1", validation_alias="OPENROUTER_BASE_URL"
    )
    default_model: str | None = Field(default=None, validation_alias="DEFAULT_MODEL")
    scientist_model: str | None = Field(default=None, validation_alias="SCIENTIST_MODEL")
    experiment_model: str | None = Field(default=None, validation_alias="EXPERIMENT_MODEL")
    runner_model: str | None = Field(default=None, validation_alias="RUNNER_MODEL")
    analyst_model: str | None = Field(default=None, validation_alias="ANALYST_MODEL")
    llm_structured_mode: StructuredMode = "auto"
    llm_max_attempts: int = Field(default=3, ge=1, le=10)
    llm_timeout_s: float = Field(default=120.0, gt=0)
    llm_temperature: float = Field(default=0.2, ge=0, le=2)

    # --- Scientific knowledge (static knowledge pack in the Scientist's prompt) -----------
    knowledge_cards_dir: Path = Path("data/knowledge/cards")
    knowledge_pack_max_chars: int = Field(default=60_000, gt=0)  # ~15k tokens

    # --- tests -------------------------------------------------------------------------------
    run_live: bool = False  # EXPSYS_RUN_LIVE=1 enables @pytest.mark.live tests

    @field_validator(
        "openrouter_api_key",
        "default_model",
        "scientist_model",
        "experiment_model",
        "runner_model",
        "analyst_model",
        mode="before",
    )
    @classmethod
    def _empty_is_unset(cls, value: Any) -> Any:
        """``KEY=`` in .env (as in .env.example) means "not set", not an empty secret."""
        if isinstance(value, str) and not value.strip():
            return None
        return value

    def model_for(self, agent: AgentName) -> str:
        """Model of one agent: its own setting, else DEFAULT_MODEL."""
        model = getattr(self, f"{agent}_model") or self.default_model
        if not model:
            raise ConfigError(
                f"no model configured for agent {agent!r}: set {agent.upper()}_MODEL or "
                "DEFAULT_MODEL (see .env.example)"
            )
        return str(model)


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings instance (created once, then cached)."""
    return Settings()
