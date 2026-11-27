"""Application wiring: build every component for one run and execute it.

Used by the CLI and by the end-to-end tests, so both exercise exactly the same assembly.
"""

from dataclasses import dataclass
from pathlib import Path

from experimental_system.backends.simulation import SimulationBackend, SimulationWorld
from experimental_system.config import Settings
from experimental_system.devices.yaml_registry import YamlDeviceRegistry
from experimental_system.knowledge.cards import (
    CardDirectorySource,
    KnowledgePack,
    load_knowledge_pack,
)
from experimental_system.llm.factory import LLMKind, build_clients, preflight
from experimental_system.llm.tracking import CallBudget
from experimental_system.orchestrator import Approver, Orchestrator, OrchestratorDeps
from experimental_system.scenarios import Scenario
from experimental_system.schemas.common import new_id, utc_now
from experimental_system.schemas.state import ExperimentState
from experimental_system.schemas.task import TaskRequest
from experimental_system.storage.run_store import RunStore


@dataclass(frozen=True)
class RunResult:
    state: ExperimentState
    store: RunStore


def new_experiment_id() -> str:
    return f"{utc_now():%Y%m%d-%H%M%S}-{new_id()[:6]}"


def knowledge_pack(settings: Settings) -> KnowledgePack:
    """The Scientist's knowledge pack from the configured cards directory (validated)."""
    return load_knowledge_pack(
        CardDirectorySource(settings.knowledge_cards_dir),
        max_chars=settings.knowledge_pack_max_chars,
    )


def run_task(
    task: TaskRequest,
    *,
    settings: Settings,
    llm_kind: LLMKind,
    knowledge: KnowledgePack | None = None,
    scenario: Scenario | None = None,
    max_iterations: int | None = None,
    approver: Approver | None = None,
    experiment_id: str | None = None,
    runs_dir: Path | None = None,
) -> RunResult:
    preflight(llm_kind, settings)
    knowledge = knowledge or knowledge_pack(settings)  # fails before a run dir exists
    experiment_id = experiment_id or new_experiment_id()
    store = RunStore(runs_dir or settings.runs_dir, experiment_id)
    registry = YamlDeviceRegistry.from_file(settings.registry_path)
    world = scenario.world if scenario is not None else SimulationWorld()
    backend = SimulationBackend(registry, world, store)
    budget = CallBudget(limit=settings.max_llm_calls)
    llms = build_clients(
        llm_kind,
        settings,
        sink=lambda entry: store.append_jsonl("llm_calls.jsonl", entry),
        budget=budget,
        fake_responses=scenario.llm if scenario is not None else None,
    )
    iterations = (
        max_iterations
        or task.max_iterations
        or (scenario.max_iterations if scenario is not None else None)
        or settings.max_iterations
    )
    orchestrator = Orchestrator(
        OrchestratorDeps(
            llms=llms,
            knowledge=knowledge,
            registry=registry,
            backend=backend,
            store=store,
            budget=budget,
            approver=approver,
        )
    )
    state = orchestrator.run(task, max_iterations=iterations, experiment_id=experiment_id)
    return RunResult(state=state, store=store)


def scenario_task(scenario: Scenario, description: str | None = None) -> TaskRequest:
    return TaskRequest(
        description=description or scenario.task.description,
        task_type_hint=scenario.task.task_type_hint,
    )
