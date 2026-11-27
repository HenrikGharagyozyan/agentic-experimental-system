"""Command-line interface: ``uv run expsys ...`` (run from the repository root)."""

import logging
from collections.abc import Sequence
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from experimental_system.app import build_knowledge_base, run_task, scenario_task
from experimental_system.config import ConfigError, Settings
from experimental_system.knowledge.ingest import ingest as ingest_fragments
from experimental_system.knowledge.memory import InMemoryKnowledgeBase
from experimental_system.scenarios import ScenarioError, list_scenarios, load_scenario
from experimental_system.schemas.devices import DeviceCommand
from experimental_system.schemas.state import ExperimentState
from experimental_system.schemas.task import TaskRequest
from experimental_system.storage.run_store import RunStore, StorageError

app = typer.Typer(
    help="Agentic Experimental System: autonomous experiments in simulation.",
    no_args_is_help=True,
    add_completion=False,
)


class LLMChoice(StrEnum):
    fake = "fake"
    openrouter = "openrouter"


class KBChoice(StrEnum):
    memory = "memory"
    pinecone = "pinecone"


def _settings() -> Settings:
    settings = Settings()
    logging.basicConfig(level=settings.log_level, format="%(levelname)s %(name)s: %(message)s")
    return settings


def _fail(message: str) -> typer.Exit:
    typer.secho(f"Ошибка: {message}", fg=typer.colors.RED, err=True)
    return typer.Exit(code=1)


@app.command()
def ingest(
    papers_dir: Annotated[Path, typer.Argument(help="Directory with PDF papers")] = Path(
        "data/papers"
    ),
    kb: Annotated[KBChoice, typer.Option(help="Where to index")] = KBChoice.memory,
    cards_dir: Annotated[Path | None, typer.Option(help="Knowledge cards directory")] = None,
) -> None:
    """Index PDF papers + knowledge cards into the Knowledge Base."""
    settings = _settings()
    fragments = ingest_fragments(papers_dir, cards_dir or settings.kb_cards_dir)
    papers = {f.metadata.get("file") for f in fragments if f.metadata.get("kind") == "paper"}
    cards = sum(1 for f in fragments if f.metadata.get("kind") == "card")
    if kb is KBChoice.memory:
        InMemoryKnowledgeBase(fragments).save_jsonl(settings.kb_index_path)
        where = str(settings.kb_index_path)
    else:
        from experimental_system.knowledge.pinecone_kb import PineconeKnowledgeBase

        try:
            index = PineconeKnowledgeBase.from_settings(settings, create=True)
        except ConfigError as exc:
            raise _fail(str(exc)) from exc
        index.upsert(fragments)
        where = (
            f"Pinecone index {settings.pinecone_index!r}, namespace {settings.pinecone_namespace!r}"
        )
    typer.echo(
        f"Проиндексировано фрагментов: {len(fragments)} (статей: {len(papers)}, карточек: {cards})"
        f" -> {where}"
    )


@app.command()
def scenarios() -> None:
    """List the available scenarios."""
    for sc in list_scenarios(_settings().scenarios_dir):
        typer.echo(f"{sc.name:26s} {sc.summary}")


def _confirm(commands: Sequence[DeviceCommand]) -> bool:
    typer.echo("\nКоманды к выполнению (уже проверены Safety Validator):")
    for i, c in enumerate(commands, 1):
        params = ", ".join(
            f"{k}={p.value}{' ' + p.unit if p.unit else ''}" for k, p in c.parameters.items()
        )
        typer.echo(f"  {i:2d}. [{c.step_id}] {c.device_id}.{c.operation}({params})")
    return typer.confirm("Выполнить?", default=False)


@app.command()
def run(
    task: Annotated[
        str | None, typer.Argument(help="Task text (default: the scenario's task)")
    ] = None,
    llm: Annotated[LLMChoice, typer.Option(help="LLM backend")] = LLMChoice.fake,
    kb: Annotated[KBChoice, typer.Option(help="Knowledge Base")] = KBChoice.memory,
    scenario: Annotated[
        str | None, typer.Option(help="Scenario: simulated world (+ scripted answers for fake)")
    ] = None,
    max_iterations: Annotated[int | None, typer.Option(min=1, help="Iteration limit")] = None,
    approve: Annotated[
        bool | None, typer.Option("--approve/--no-approve", help="Confirm before each execute")
    ] = None,
) -> None:
    """Run the autonomous experiment loop in simulation."""
    settings = _settings()
    sc = None
    if scenario is not None:
        try:
            sc = load_scenario(settings.scenarios_dir, scenario)
        except ScenarioError as exc:
            raise _fail(str(exc)) from exc
    if llm is LLMChoice.fake and sc is None:
        raise _fail("--llm fake needs --scenario (scripted answers); see `expsys scenarios`")
    if task is None and sc is None:
        raise _fail("give a task text or --scenario")
    if llm is LLMChoice.fake and task is not None:
        typer.secho(
            "Внимание: FakeLLM отвечает по сценарию, текст задачи на ответы не влияет.",
            fg=typer.colors.YELLOW,
        )
    request = scenario_task(sc, task) if sc is not None else TaskRequest(description=task or "")
    need_approval = settings.require_approval if approve is None else approve
    try:
        knowledge = build_knowledge_base(kb.value, settings)
        result = run_task(
            request,
            settings=settings,
            llm_kind=llm.value,
            kb=knowledge,
            scenario=sc,
            max_iterations=max_iterations,
            approver=_confirm if need_approval else None,
        )
    except ConfigError as exc:
        raise _fail(str(exc)) from exc
    _print_summary(result.state, result.store.dir)


@app.command()
def show(experiment_id: Annotated[str, typer.Argument(help="Run id (directory in runs/)")]) -> None:
    """Short summary of a finished run."""
    settings = _settings()
    run_dir = settings.runs_dir / experiment_id
    if not run_dir.is_dir():
        raise _fail(f"no run {experiment_id!r} in {settings.runs_dir}")
    try:
        state = RunStore(settings.runs_dir, experiment_id).load_state()
    except StorageError as exc:
        raise _fail(str(exc)) from exc
    _print_summary(state, run_dir)


def _print_summary(state: ExperimentState, run_dir: Path) -> None:
    color = typer.colors.GREEN if state.status.value == "DONE" else typer.colors.YELLOW
    typer.secho(f"\nЭксперимент {state.experiment_id}: {state.status.value}", fg=color, bold=True)
    typer.echo(f"Задача: {state.task.description}")
    typer.echo(
        f"Итераций: {len(state.history)} / {state.max_iterations}, вызовов LLM: {state.llm_calls}"
    )
    for record in state.history:
        decision = record.analysis.decision.value if record.analysis else "—"
        status = record.execution.status.value if record.execution else "не выполнялось"
        criteria = ""
        if record.metrics is not None:
            criteria = ", ".join(
                f"{c.criterion.metric}={'—' if c.observed is None else f'{c.observed:.4g}'}"
                f"{'✓' if c.passed else '✗'}"
                for c in record.metrics.criteria
            )
        typer.echo(
            f"  итерация {record.iteration}: исполнение {status}; {criteria}; решение {decision}"
        )
    for err in state.errors:
        typer.secho(f"  ошибка: {err}", fg=typer.colors.RED)
    for note in state.notes:
        typer.echo(f"  примечание: {note}")
    typer.echo(f"Каталог прогона: {run_dir}")
    report = run_dir / "final_report.md"
    if report.is_file():
        typer.echo(f"Отчёт: {report}")


if __name__ == "__main__":  # pragma: no cover
    app()
