"""Scenarios: task + simulated world + (optional) scripted FakeLLM responses."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import Field

from experimental_system.backends.simulation import SimulationWorld
from experimental_system.schemas.common import Contract, Identifier, NonEmptyStr


class ScenarioTask(Contract):
    description: NonEmptyStr
    task_type_hint: Identifier | None = None


class Scenario(Contract):
    name: Identifier
    summary: str = ""
    task: ScenarioTask
    max_iterations: int = Field(default=5, gt=0)
    world: SimulationWorld = Field(default_factory=SimulationWorld)
    # FakeLLM responses per agent (scientist, experiment, runner, analyst), in call order.
    llm: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)


class ScenarioError(ValueError):
    """Unknown or invalid scenario."""


def scenario_path(scenarios_dir: Path, name: str) -> Path:
    return scenarios_dir / f"{name}.yaml"


def load_scenario(scenarios_dir: Path, name: str) -> Scenario:
    path = scenario_path(scenarios_dir, name)
    if not path.is_file():
        known = sorted(p.stem for p in scenarios_dir.glob("*.yaml"))
        raise ScenarioError(f"unknown scenario {name!r}; known: {known}")
    return Scenario.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def list_scenarios(scenarios_dir: Path) -> list[Scenario]:
    return [load_scenario(scenarios_dir, p.stem) for p in sorted(scenarios_dir.glob("*.yaml"))]
