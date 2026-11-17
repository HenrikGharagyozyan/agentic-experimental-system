"""Metrics and AnalysisReport."""

import pytest
from pydantic import ValidationError

from experimental_system.schemas import AnalysisReport, CriterionResult, Decision, Metrics
from factories import make_criterion, make_metrics


def _result(passed: bool, observed: float | None = 0.5) -> CriterionResult:
    return CriterionResult(criterion=make_criterion(), observed=observed, passed=passed)


def test_all_criteria_met_when_every_criterion_passed() -> None:
    assert make_metrics().all_criteria_met is True


def test_all_criteria_not_met_when_one_failed() -> None:
    metrics = Metrics(values={"objective": 2.0}, criteria=[_result(True), _result(False)])
    assert metrics.all_criteria_met is False


def test_all_criteria_not_met_without_criteria() -> None:
    assert Metrics(values={"objective": 0.5}).all_criteria_met is False


def test_missing_metric_is_a_failed_criterion() -> None:
    metrics = Metrics(criteria=[_result(False, observed=None)])
    assert metrics.all_criteria_met is False


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_metrics_reject_non_finite_values(value: float) -> None:
    with pytest.raises(ValidationError):
        Metrics(values={"objective": value})


def test_metrics_round_trip_with_computed_field() -> None:
    metrics = make_metrics()
    assert Metrics.model_validate_json(metrics.model_dump_json()) == metrics


@pytest.mark.parametrize("decision", [Decision.REPLAN, Decision.REMODEL])
def test_replan_and_remodel_require_recommendations(decision: Decision) -> None:
    with pytest.raises(ValidationError, match="requires at least one recommendation"):
        AnalysisReport(decision=decision, rationale="Objective too high")


@pytest.mark.parametrize("decision", [Decision.DONE, Decision.ABORT])
def test_done_and_abort_do_not_require_recommendations(decision: Decision) -> None:
    assert AnalysisReport(decision=decision, rationale="x").decision is decision


def test_decision_parsed_from_llm_json() -> None:
    report = AnalysisReport.model_validate_json(
        '{"decision": "REPLAN", "rationale": "x", "recommendations": ["more samples"]}'
    )
    assert report.decision is Decision.REPLAN


def test_unknown_decision_is_rejected() -> None:
    with pytest.raises(ValidationError):
        AnalysisReport.model_validate({"decision": "MAYBE", "rationale": "x"})
