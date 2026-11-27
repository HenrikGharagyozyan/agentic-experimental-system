"""Criteria evaluation and catalog consistency."""

import pytest

from experimental_system.schemas import SuccessCriterion
from experimental_system.scientific_core.catalog import METRICS, describe_metrics
from experimental_system.scientific_core.evaluation import evaluate_criteria


@pytest.mark.parametrize(
    ("op", "target", "passed"),
    [("<", 1.0, True), ("<=", 0.5, True), (">", 0.5, False), (">=", 0.5, True), ("<", 0.5, False)],
)
def test_operators(op: str, target: float, passed: bool) -> None:
    criterion = SuccessCriterion.model_validate(
        {"metric": "energy_gap", "op": op, "target": target}
    )
    [result] = evaluate_criteria({"energy_gap": 0.5}, [criterion])
    assert result.passed is passed
    assert result.observed == 0.5


def test_missing_metric_fails() -> None:
    criterion = SuccessCriterion(metric="enhancement", op=">=", target=10)
    [result] = evaluate_criteria({}, [criterion])
    assert result.observed is None and not result.passed


def test_catalog_description_lists_every_metric() -> None:
    text = describe_metrics()
    assert all(f"- {name} " in text for name in METRICS)
