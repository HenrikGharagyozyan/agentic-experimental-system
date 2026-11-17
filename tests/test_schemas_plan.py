"""ExperimentPlan and PlanStep."""

import pytest
from pydantic import ValidationError

from experimental_system.schemas import ExperimentPlan
from factories import make_plan


def test_valid_plan_round_trip() -> None:
    plan = make_plan()
    assert ExperimentPlan.model_validate_json(plan.model_dump_json()) == plan


def test_plan_requires_steps() -> None:
    with pytest.raises(ValidationError):
        ExperimentPlan(rationale="x", steps=[])


def test_plan_rejects_duplicate_step_ids() -> None:
    data = make_plan().model_dump()
    data["steps"][1]["step_id"] = "s1"
    data["steps"][1]["depends_on"] = []
    with pytest.raises(ValidationError, match="duplicate step_id"):
        ExperimentPlan.model_validate(data)


def test_plan_rejects_dependency_on_unknown_step() -> None:
    data = make_plan().model_dump()
    data["steps"][1]["depends_on"] = ["s99"]
    with pytest.raises(ValidationError, match="not an earlier step"):
        ExperimentPlan.model_validate(data)


def test_plan_rejects_dependency_on_later_step() -> None:
    data = make_plan().model_dump()
    data["steps"][0]["depends_on"] = ["s2"]
    with pytest.raises(ValidationError, match="not an earlier step"):
        ExperimentPlan.model_validate(data)
