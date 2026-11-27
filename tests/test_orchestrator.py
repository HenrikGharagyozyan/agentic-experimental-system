"""End-to-end runs of the orchestrator with FakeLLM scenarios and failure paths."""

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from experimental_system.app import build_knowledge_base, run_task, scenario_task
from experimental_system.config import Settings
from experimental_system.knowledge import KnowledgeBase
from experimental_system.scenarios import Scenario, ScenarioError, list_scenarios, load_scenario
from experimental_system.schemas import Decision, DeviceCommand, ExperimentStatus

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def settings() -> Settings:
    return Settings(
        _env_file=None,
        registry_path=REPO / "configs/devices/simulation.yaml",
        scenarios_dir=REPO / "configs/scenarios",
        kb_cards_dir=REPO / "data/knowledge/cards",
        kb_index_path=REPO / "does-not-exist.jsonl",  # cards-only KB: independent of local index
    )


@pytest.fixture(scope="module")
def kb(settings: Settings) -> KnowledgeBase:
    return build_knowledge_base("memory", settings)


def _run(
    name: str,
    settings: Settings,
    kb: KnowledgeBase,
    tmp_path: Path,
    *,
    scenario: Scenario | None = None,
    **kwargs: Any,
) -> Any:
    sc = scenario or load_scenario(settings.scenarios_dir, name)
    return run_task(
        scenario_task(sc),
        settings=settings,
        llm_kind="fake",
        kb=kb,
        scenario=sc,
        runs_dir=tmp_path,
        experiment_id="exp",
        **kwargs,
    )


def _modified(settings: Settings, name: str, **llm: list[dict[str, Any]]) -> Scenario:
    sc = load_scenario(settings.scenarios_dir, name)
    data = sc.model_dump(mode="json")
    data["llm"].update(llm)
    return Scenario.model_validate(data)


def test_all_scenarios_load(settings: Settings) -> None:
    names = {s.name for s in list_scenarios(settings.scenarios_dir)}
    assert {
        "ising_ground_state",
        "tm_calibration_focusing",
        "two_foci_coupling",
        "runner_out_of_range",
    } <= names
    with pytest.raises(ScenarioError, match="known"):
        load_scenario(settings.scenarios_dir, "nope")


def test_ising_ground_state_replan_then_done(
    settings: Settings, kb: KnowledgeBase, tmp_path: Path
) -> None:
    result = _run("ising_ground_state", settings, kb, tmp_path)
    state = result.state
    assert state.status is ExperimentStatus.DONE, state.errors
    first, second = state.history
    assert first.analysis is not None and first.analysis.decision is Decision.REPLAN
    assert first.metrics is not None and not first.metrics.all_criteria_met
    assert second.metrics is not None and second.metrics.all_criteria_met
    assert second.metrics.values["energy_gap"] < 1e-9
    # persistence
    run_dir = result.store.dir
    assert (run_dir / "state.json").is_file()
    assert sorted(p.name for p in (run_dir / "iterations").iterdir()) == [
        "iter_00.json",
        "iter_01.json",
    ]
    assert any((run_dir / "arrays").glob("it01_*replicas.npy"))
    calls = [json.loads(line) for line in (run_dir / "llm_calls.jsonl").read_text().splitlines()]
    assert [c["agent"] for c in calls] == [
        "scientist",
        "experiment",
        "runner",
        "analyst",
        "experiment",
        "runner",
        "analyst",
    ]
    assert state.llm_calls == 7
    report = (run_dir / "final_report.md").read_text()
    assert "Итерация 1" in report and "card:ground_state_search" in report
    assert "energy_gap" in report and "REPLAN" in report


def test_replan_context_contains_previous_plan_and_recommendations(
    settings: Settings, kb: KnowledgeBase, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Memory between iterations: on REPLAN the Experiment agent sees plan + history."""
    from experimental_system.llm import FakeLLM

    seen: list[str] = []
    original = FakeLLM.generate

    def spy(self: FakeLLM, messages: Sequence[Any], response_model: Any) -> Any:
        if self.agent == "experiment":
            seen.append(messages[1].content)
        return original(self, messages, response_model)

    monkeypatch.setattr(FakeLLM, "generate", spy)
    _run("ising_ground_state", settings, kb, tmp_path)
    assert "previous_plan" not in seen[0]
    assert "previous_plan" in seen[1] and "Increase n_iterations" in seen[1]
    assert '"history"' in seen[1] and "energy_gap" in seen[1]


def test_tm_calibration_focusing(settings: Settings, kb: KnowledgeBase, tmp_path: Path) -> None:
    state = _run("tm_calibration_focusing", settings, kb, tmp_path).state
    assert state.status is ExperimentStatus.DONE, state.errors
    metrics = state.history[-1].metrics
    assert metrics is not None
    values = metrics.values
    assert values["enhancement_ratio"] >= 0.6
    assert values["tm_correlation"] > 0.9


def test_two_foci_coupling(settings: Settings, kb: KnowledgeBase, tmp_path: Path) -> None:
    state = _run("two_foci_coupling", settings, kb, tmp_path).state
    assert state.status is ExperimentStatus.DONE, state.errors
    metrics = state.history[-1].metrics
    assert metrics is not None
    values = metrics.values
    assert values["replica_overlap_change"] >= 0.2


def test_runner_out_of_range_is_rejected_then_fixed(
    settings: Settings, kb: KnowledgeBase, tmp_path: Path
) -> None:
    state = _run("runner_out_of_range", settings, kb, tmp_path).state
    assert state.status is ExperimentStatus.DONE, state.errors
    record = state.history[0]
    assert record.runner_corrections == 1
    assert all(v.accepted for v in record.validations)
    power = record.validations[0].command.parameters["power"].value
    assert power == 50.0  # the corrected value, never a clamped one
    assert any("500.0 mW is outside" in n for n in state.notes)


def test_runner_never_fixes_command_fails(
    settings: Settings, kb: KnowledgeBase, tmp_path: Path
) -> None:
    bad = load_scenario(settings.scenarios_dir, "runner_out_of_range").llm["runner"][0]
    sc = _modified(settings, "runner_out_of_range", runner=[bad, bad, bad])
    state = _run("", settings, kb, tmp_path, scenario=sc).state
    assert state.status is ExperimentStatus.FAILED
    assert "after 2 corrections" in state.errors[-1]
    assert state.history and state.history[0].execution is None  # nothing executed


def test_iteration_limit(settings: Settings, kb: KnowledgeBase, tmp_path: Path) -> None:
    state = _run("ising_ground_state", settings, kb, tmp_path, max_iterations=1).state
    assert state.status is ExperimentStatus.ITERATION_LIMIT
    assert len(state.history) == 1


def test_llm_call_budget(settings: Settings, kb: KnowledgeBase, tmp_path: Path) -> None:
    tight = settings.model_copy(update={"max_llm_calls": 3})
    state = _run("ising_ground_state", tight, kb, tmp_path).state
    assert state.status is ExperimentStatus.FAILED
    assert "LLM call budget exhausted" in state.errors[-1]
    assert (tmp_path / "exp" / "final_report.md").is_file()


def test_exhausted_fake_llm_fails_with_history(
    settings: Settings, kb: KnowledgeBase, tmp_path: Path
) -> None:
    sc = load_scenario(settings.scenarios_dir, "ising_ground_state")
    data = sc.model_dump(mode="json")
    data["llm"]["analyst"] = data["llm"]["analyst"][:1]  # no second analyst answer
    state = _run("", settings, kb, tmp_path, scenario=Scenario.model_validate(data)).state
    assert state.status is ExperimentStatus.FAILED
    assert "exhausted" in state.errors[-1]
    assert len(state.history) == 2  # partial second iteration kept
    assert state.history[1].execution is not None and state.history[1].analysis is None


def test_done_overridden_when_criteria_unmet(
    settings: Settings, kb: KnowledgeBase, tmp_path: Path
) -> None:
    sc = load_scenario(settings.scenarios_dir, "ising_ground_state")
    data = sc.model_dump(mode="json")
    data["llm"]["analyst"][0] = {"decision": "DONE", "rationale": "looks good to me"}
    state = _run("", settings, kb, tmp_path, scenario=Scenario.model_validate(data)).state
    assert state.status is ExperimentStatus.DONE  # done only after the second iteration
    assert state.history[0].analysis is not None
    assert state.history[0].analysis.decision is Decision.REPLAN
    assert any("not all success criteria are met" in n for n in state.notes)


def test_approval_rejected_aborts(settings: Settings, kb: KnowledgeBase, tmp_path: Path) -> None:
    asked: list[int] = []

    def deny(commands: Sequence[DeviceCommand]) -> bool:
        asked.append(len(commands))
        return False

    state = _run("tm_calibration_focusing", settings, kb, tmp_path, approver=deny).state
    assert state.status is ExperimentStatus.ABORTED
    assert asked == [5]
    assert state.history[0].execution is None


def test_approval_granted_runs(settings: Settings, kb: KnowledgeBase, tmp_path: Path) -> None:
    state = _run("runner_out_of_range", settings, kb, tmp_path, approver=lambda c: True).state
    assert state.status is ExperimentStatus.DONE
