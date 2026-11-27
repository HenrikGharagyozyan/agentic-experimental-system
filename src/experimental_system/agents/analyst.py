"""Analyst agent: specification + Metrics + execution summary -> AnalysisReport.

Code rules after the LLM:
- every referenced metric must exist in Metrics.values (else retry);
- DONE is accepted only if Metrics.all_criteria_met; otherwise it becomes REPLAN with a
  code-generated recommendation listing the failed criteria.
"""

from dataclasses import dataclass, field
from typing import Any

from experimental_system.agents.common import ask_checked, load_prompt
from experimental_system.agents.context import execution_summary, metrics_summary, plan_summary
from experimental_system.llm.base import LLMClient
from experimental_system.schemas.analysis import AnalysisReport, Decision, Metrics
from experimental_system.schemas.execution import ExecutionResult
from experimental_system.schemas.plan import ExperimentPlan
from experimental_system.schemas.task import ScientificSpecification


@dataclass(frozen=True)
class AnalystInput:
    specification: ScientificSpecification
    plan: ExperimentPlan
    execution: ExecutionResult
    metrics: Metrics
    history: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class AnalystOutput:
    report: AnalysisReport
    override_note: str | None = None  # set when code changed the LLM's decision


def run_analyst(llm: LLMClient, inp: AnalystInput) -> AnalystOutput:
    payload: dict[str, Any] = {
        "specification": inp.specification,
        "plan": plan_summary(inp.plan),
        "execution": execution_summary(inp.execution),
        "metrics": metrics_summary(inp.metrics),
    }
    if inp.history:
        payload["history"] = inp.history
    available = set(inp.metrics.values)

    def check(report: AnalysisReport) -> list[str]:
        return [
            f"referenced metric {name!r} was not computed; available: {sorted(available)}"
            for name in report.referenced_metrics
            if name not in available
        ]

    report = ask_checked(
        llm,
        agent="analyst",
        system=load_prompt("analyst"),
        payload=payload,
        response_model=AnalysisReport,
        check=check,
    )
    if report.decision is Decision.DONE and not inp.metrics.all_criteria_met:
        failed = [
            f"{c.criterion.metric} {c.criterion.op} {c.criterion.target} "
            f"(observed: {'missing' if c.observed is None else c.observed})"
            for c in inp.metrics.criteria
            if not c.passed
        ] or ["no success criteria were evaluated"]
        note = "Analyst chose DONE, but not all success criteria are met -> REPLAN (code rule)."
        report = AnalysisReport(
            decision=Decision.REPLAN,
            rationale=f"{report.rationale}\n[{note}]",
            anomalies=report.anomalies,
            recommendations=[
                *report.recommendations,
                "Unmet success criteria: " + "; ".join(failed),
            ],
            referenced_metrics=report.referenced_metrics,
        )
        return AnalystOutput(report=report, override_note=note)
    return AnalystOutput(report=report)
