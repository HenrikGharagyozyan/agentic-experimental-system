"""Experiment agent: specification + device/procedure overview -> ExperimentPlan."""

from dataclasses import dataclass, field
from typing import Any

from experimental_system.agents.common import ask_checked, load_prompt
from experimental_system.agents.context import plan_summary
from experimental_system.devices.registry import DeviceRegistry
from experimental_system.llm.base import LLMClient
from experimental_system.schemas.analysis import AnalysisReport
from experimental_system.schemas.plan import ExperimentPlan
from experimental_system.schemas.task import ScientificSpecification


@dataclass(frozen=True)
class ExperimentInput:
    specification: ScientificSpecification
    previous_plan: ExperimentPlan | None = None
    analyst_feedback: AnalysisReport | None = None  # set on REPLAN
    history: list[dict[str, Any]] = field(default_factory=list)


def device_overview(registry: DeviceRegistry) -> list[dict[str, Any]]:
    """Devices and their operations WITHOUT parameter ranges (those are the Runner's job)."""
    return [
        {
            "device_id": d.device_id,
            "kind": d.kind,
            "description": d.description,
            "operations": [
                {
                    "name": o.name,
                    "description": o.description,
                    "parameters": [p.name for p in o.parameters],
                }
                for o in d.operations
            ],
        }
        for d in registry.list_devices()
    ]


def _comparable(plan: ExperimentPlan) -> list[dict[str, Any]]:
    return plan_summary(plan)["steps"]  # type: ignore[no-any-return]


def run_experiment(
    llm: LLMClient, registry: DeviceRegistry, inp: ExperimentInput
) -> ExperimentPlan:
    payload: dict[str, Any] = {
        "specification": inp.specification,
        "devices": device_overview(registry),
    }
    if inp.previous_plan is not None:
        payload["previous_plan"] = plan_summary(inp.previous_plan)
    if inp.analyst_feedback is not None:
        payload["analyst_feedback"] = {
            "decision": inp.analyst_feedback.decision.value,
            "rationale": inp.analyst_feedback.rationale,
            "recommendations": inp.analyst_feedback.recommendations,
        }
    if inp.history:
        payload["history"] = inp.history

    def check(plan: ExperimentPlan) -> list[str]:
        problems = []
        for step in plan.steps:
            for device in step.devices:
                if registry.get_device(device) is None:
                    problems.append(f"step {step.step_id!r}: unknown device {device!r}")
        if inp.previous_plan is not None and _comparable(plan) == _comparable(inp.previous_plan):
            problems.append(
                "the new plan is identical to the previous (failed) plan; change it according "
                "to the analyst recommendations"
            )
        return problems

    return ask_checked(
        llm,
        agent="experiment",
        system=load_prompt("experiment"),
        payload=payload,
        response_model=ExperimentPlan,
        check=check,
    )
