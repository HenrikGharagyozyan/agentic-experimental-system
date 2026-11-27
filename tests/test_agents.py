"""Agents with FakeLLM: code checks, feedback retries, DONE override, memory."""

from typing import Any

import pytest

from experimental_system.agents import (
    AgentError,
    AnalystInput,
    ExperimentInput,
    ScientistInput,
    device_overview,
    run_analyst,
    run_experiment,
    run_runner,
    run_scientist,
    scientist_system_prompt,
)
from experimental_system.agents.common import load_prompt
from experimental_system.devices import YamlDeviceRegistry
from experimental_system.knowledge import build_knowledge_pack
from experimental_system.llm import FakeLLM
from experimental_system.schemas import (
    CriterionResult,
    Decision,
    KnowledgeCard,
    Metrics,
    SuccessCriterion,
    TaskRequest,
)
from factories import make_execution, make_plan, make_report, make_spec

PACK = build_knowledge_pack(
    [
        KnowledgeCard(card_id="ising", title="Optical Ising", source="Delloye", body="H = -I"),
        KnowledgeCard(card_id="ggs", title="GGS", source="Huang", body="X_f = (P^+ E_f)^T"),
    ]
)
TASK = TaskRequest(description="Find the optical ising ground state")


def _spec(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "objective": "Minimise H",
        "task_type": "ising_ground_state",
        "math_model": {"description": "H = -I", "equations": ["H = -sum I_m"]},
        "success_criteria": [{"metric": "energy_gap", "op": "<=", "target": 0.01}],
        "citations": [{"card_id": "ising"}],
    }
    data.update(overrides)
    return data


def test_prompts_exist() -> None:
    for name in ("scientist", "experiment", "runner", "analyst"):
        assert "# Role" in load_prompt(name)


def test_scientist_happy_path_pack_in_system_prompt_no_devices() -> None:
    llm = FakeLLM("scientist", [_spec()])
    spec = run_scientist(llm, PACK, ScientistInput(task=TASK))
    assert spec.task_type == "ising_ground_state"
    system, user = llm.calls[0][0].content, llm.calls[0][1].content
    assert system == scientist_system_prompt(PACK)
    assert system.endswith(PACK.text) and "Card `ggs`" in system
    assert "available_metrics" in user and "knowledge" not in user
    assert "sim_laser" not in system + user and "device_id" not in system + user


def test_scientist_unknown_card_and_metric_are_retried() -> None:
    bad = _spec(
        citations=[{"card_id": "made_up"}],
        success_criteria=[{"metric": "happiness", "op": ">", "target": 1}],
    )
    llm = FakeLLM("scientist", [bad, _spec()])
    spec = run_scientist(llm, PACK, ScientistInput(task=TASK))
    assert spec.citations[0].card_id == "ising"
    feedback = llm.calls[1][-1].content
    assert "made_up" in feedback and "happiness" in feedback and "valid card ids" in feedback


def test_scientist_gives_up_without_citations() -> None:
    bad = _spec(citations=[])
    with pytest.raises(AgentError, match="scientist"):
        run_scientist(FakeLLM("scientist", [bad, bad, bad]), PACK, ScientistInput(task=TASK))


def test_scientist_remodel_must_change_spec() -> None:
    previous = run_scientist(FakeLLM("scientist", [_spec()]), PACK, ScientistInput(task=TASK))
    feedback = make_report().model_copy(
        update={"decision": Decision.REMODEL, "recommendations": ["reformulate"]}
    )
    llm = FakeLLM("scientist", [_spec(), _spec(objective="New objective")])
    inp = ScientistInput(task=TASK, previous_specification=previous, analyst_feedback=feedback)
    assert run_scientist(llm, PACK, inp).objective == "New objective"
    assert "previous_specification" in llm.calls[0][1].content


def _plan(n_iterations: int = 10, devices: list[str] | None = None) -> dict[str, Any]:
    return {
        "rationale": "light on, optimise",
        "steps": [
            {
                "step_id": "s1",
                "action": "optimize",
                "description": "run optimisation",
                "devices": devices or ["sim_laser", "procedures"],
                "parameters": {"n_iterations": n_iterations},
            }
        ],
    }


def test_experiment_sees_operations_but_not_ranges(sim_registry: YamlDeviceRegistry) -> None:
    overview = str(device_overview(sim_registry))
    assert "run_ising_optimization" in overview and "maximum" not in overview
    llm = FakeLLM("experiment", [_plan(devices=["sim_laser", "laser_9000"]), _plan()])
    plan = run_experiment(llm, sim_registry, ExperimentInput(specification=make_spec()))
    assert plan.steps[0].devices == ["sim_laser", "procedures"]
    assert "laser_9000" in llm.calls[1][-1].content


def test_experiment_replan_must_change_plan(sim_registry: YamlDeviceRegistry) -> None:
    from experimental_system.schemas import ExperimentPlan

    previous = ExperimentPlan.model_validate(_plan(10))
    feedback = make_report().model_copy(
        update={"decision": Decision.REPLAN, "recommendations": ["more iterations"]}
    )
    llm = FakeLLM("experiment", [_plan(10), _plan(200)])
    inp = ExperimentInput(
        specification=make_spec(),
        previous_plan=previous,
        analyst_feedback=feedback,
        history=[{"iteration": 0, "decision": "REPLAN"}],
    )
    plan = run_experiment(llm, sim_registry, inp)
    assert plan.steps[0].parameters["n_iterations"] == 200
    first_context = llm.calls[0][1].content
    assert "previous_plan" in first_context and "more iterations" in first_context
    assert "identical" in llm.calls[1][-1].content


def test_runner_gets_full_registry_and_checks_steps(sim_registry: YamlDeviceRegistry) -> None:
    from experimental_system.schemas import DeviceStatus, ExperimentPlan

    plan = ExperimentPlan.model_validate(_plan())
    wrong_step = {
        "commands": [
            {
                "step_id": "s9",
                "device_id": "sim_laser",
                "operation": "set_emission",
                "parameters": {"enabled": {"value": True}},
            }
        ]
    }
    good = {"commands": [{**wrong_step["commands"][0], "step_id": "s1"}]}
    llm = FakeLLM("runner", [wrong_step, good])
    statuses = [DeviceStatus(device_id="sim_laser", state="ok")]
    batch = run_runner(llm, sim_registry, plan, statuses)
    assert batch.commands[0].step_id == "s1"
    assert '"maximum": 50.0' in llm.calls[0][1].content  # full registry incl. ranges


def _metrics(passed: bool) -> Metrics:
    criterion = SuccessCriterion(metric="objective", op="<=", target=1.0)
    observed = 0.5 if passed else 3.0
    return Metrics(
        values={"objective": observed},
        criteria=[CriterionResult(criterion=criterion, observed=observed, passed=passed)],
    )


def _analyst_input(passed: bool) -> AnalystInput:
    return AnalystInput(
        specification=make_spec(),
        plan=make_plan(),
        execution=make_execution(),
        metrics=_metrics(passed),
    )


def test_analyst_done_accepted_when_criteria_met() -> None:
    llm = FakeLLM(
        "analyst", [{"decision": "DONE", "rationale": "met", "referenced_metrics": ["objective"]}]
    )
    out = run_analyst(llm, _analyst_input(True))
    assert out.report.decision is Decision.DONE and out.override_note is None


def test_analyst_done_overridden_when_criteria_not_met() -> None:
    llm = FakeLLM("analyst", [{"decision": "DONE", "rationale": "looks fine"}])
    out = run_analyst(llm, _analyst_input(False))
    assert out.report.decision is Decision.REPLAN
    assert out.override_note is not None
    assert any("objective <= 1.0 (observed: 3.0)" in r for r in out.report.recommendations)


def test_analyst_unknown_referenced_metric_is_retried() -> None:
    llm = FakeLLM(
        "analyst",
        [
            {"decision": "DONE", "rationale": "x", "referenced_metrics": ["accuracy"]},
            {"decision": "DONE", "rationale": "x", "referenced_metrics": ["objective"]},
        ],
    )
    assert run_analyst(llm, _analyst_input(True)).report.referenced_metrics == ["objective"]
    assert "accuracy" in llm.calls[1][-1].content
