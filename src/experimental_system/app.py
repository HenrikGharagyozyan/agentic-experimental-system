"""Application wiring: build every component for one run and execute it.

Used by the CLI and by the end-to-end tests, so both exercise exactly the same assembly.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from experimental_system.backends.simulation import SimulationBackend, SimulationWorld
from experimental_system.config import Settings
from experimental_system.devices.yaml_registry import YamlDeviceRegistry
from experimental_system.knowledge.base import KnowledgeBase
from experimental_system.knowledge.ingest import ingest
from experimental_system.knowledge.memory import InMemoryKnowledgeBase
from experimental_system.llm.factory import LLMKind, build_clients
from experimental_system.llm.tracking import CallBudget
from experimental_system.orchestrator import Approver, Orchestrator, OrchestratorDeps
from experimental_system.scenarios import Scenario
from experimental_system.schemas.common import new_id, utc_now
from experimental_system.schemas.state import ExperimentState
from experimental_system.schemas.task import TaskRequest
from experimental_system.storage.run_store import RunStore

KBKind = Literal["memory", "pinecone"]


@dataclass(frozen=True)
class RunResult:
    state: ExperimentState
    store: RunStore


def new_experiment_id() -> str:
    return f"{utc_now():%Y%m%d-%H%M%S}-{new_id()[:6]}"


def build_knowledge_base(kind: KBKind, settings: Settings) -> KnowledgeBase:
    if kind == "pinecone":
        from experimental_system.knowledge.pinecone_kb import PineconeKnowledgeBase

        return PineconeKnowledgeBase.from_settings(settings)
    if settings.kb_index_path.is_file():
        return InMemoryKnowledgeBase.load_jsonl(settings.kb_index_path)
    # No local index yet (`expsys ingest` not run): use the curated cards only.
    return InMemoryKnowledgeBase(ingest(None, settings.kb_cards_dir))


def run_task(
    task: TaskRequest,
    *,
    settings: Settings,
    llm_kind: LLMKind,
    kb: KnowledgeBase,
    scenario: Scenario | None = None,
    max_iterations: int | None = None,
    approver: Approver | None = None,
    experiment_id: str | None = None,
    runs_dir: Path | None = None,
) -> RunResult:
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
            kb=kb,
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
