"""Memory between iterations: compact summaries of past cycles for the agents."""

from typing import Any

from experimental_system.schemas.analysis import Metrics
from experimental_system.schemas.execution import ExecutionResult
from experimental_system.schemas.plan import ExperimentPlan
from experimental_system.schemas.state import IterationRecord


def plan_summary(plan: ExperimentPlan) -> dict[str, Any]:
    return {
        "rationale": plan.rationale,
        "steps": [
            {
                "step_id": s.step_id,
                "action": s.action,
                "devices": s.devices,
                "parameters": s.parameters,
            }
            for s in plan.steps
        ],
    }


def metrics_summary(metrics: Metrics) -> dict[str, Any]:
    return {
        "values": metrics.values,
        "criteria": [
            {
                "metric": c.criterion.metric,
                "op": c.criterion.op,
                "target": c.criterion.target,
                "observed": c.observed,
                "passed": c.passed,
            }
            for c in metrics.criteria
        ],
        "all_criteria_met": metrics.all_criteria_met,
    }


def execution_summary(execution: ExecutionResult) -> dict[str, Any]:
    """Status, errors and scalar measurements - never arrays (data_refs only by name)."""
    return {
        "backend": execution.backend,
        "status": execution.status.value,
        "errors": [e.message for e in execution.errors],
        "measurements": [
            {
                "step_id": m.step_id,
                "name": m.name,
                **({"value": m.value, "unit": m.unit} if m.data_ref is None else {"array": True}),
            }
            for m in execution.measurements
        ],
    }


def iteration_summaries(history: list[IterationRecord]) -> list[dict[str, Any]]:
    out = []
    for record in history:
        entry: dict[str, Any] = {"iteration": record.iteration}
        if record.plan is not None:
            entry["plan"] = plan_summary(record.plan)
        if record.execution is not None:
            entry["execution_status"] = record.execution.status.value
            entry["execution_errors"] = [e.message for e in record.execution.errors]
        if record.metrics is not None:
            entry["metrics"] = metrics_summary(record.metrics)
        if record.analysis is not None:
            entry["decision"] = record.analysis.decision.value
            entry["analyst_rationale"] = record.analysis.rationale
            entry["recommendations"] = record.analysis.recommendations
        out.append(entry)
    return out
