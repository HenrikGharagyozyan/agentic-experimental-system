"""Shared fixtures."""

from pathlib import Path

import pytest

from experimental_system.devices import YamlDeviceRegistry

REPO_ROOT = Path(__file__).resolve().parents[1]
SIM_REGISTRY_PATH = REPO_ROOT / "configs" / "devices" / "simulation.yaml"


@pytest.fixture
def sim_registry() -> YamlDeviceRegistry:
    return YamlDeviceRegistry.from_file(SIM_REGISTRY_PATH)
