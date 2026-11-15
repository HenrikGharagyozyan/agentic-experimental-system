"""Smoke tests: the package imports and settings are read from env / `.env`."""

from pathlib import Path

import pytest
from pydantic import ValidationError

import experimental_system
from experimental_system.config import Settings, get_settings


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove any EXPSYS_* variables from the real environment so tests are isolated."""
    for name in ("EXPSYS_APP_ENV", "EXPSYS_LOG_LEVEL"):
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()


def test_package_imports() -> None:
    assert experimental_system.__version__ == "0.1.0"


def test_defaults_without_env() -> None:
    settings = Settings(_env_file=None)
    assert settings.app_env == "dev"
    assert settings.log_level == "INFO"


def test_reads_environment_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXPSYS_APP_ENV", "test")
    monkeypatch.setenv("EXPSYS_LOG_LEVEL", "DEBUG")
    settings = Settings(_env_file=None)
    assert settings.app_env == "test"
    assert settings.log_level == "DEBUG"


def test_reads_dotenv_file(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("EXPSYS_LOG_LEVEL=WARNING\n", encoding="utf-8")
    settings = Settings(_env_file=env_file)
    assert settings.log_level == "WARNING"


def test_environment_overrides_dotenv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("EXPSYS_LOG_LEVEL=WARNING\n", encoding="utf-8")
    monkeypatch.setenv("EXPSYS_LOG_LEVEL", "ERROR")
    settings = Settings(_env_file=env_file)
    assert settings.log_level == "ERROR"


def test_invalid_value_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXPSYS_LOG_LEVEL", "LOUD")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_get_settings_is_cached() -> None:
    assert get_settings() is get_settings()
