"""TaskRequest and ScientificSpecification."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from experimental_system.schemas import ScientificSpecification, TaskRequest
from factories import make_spec, make_task


def test_task_created_at_is_timezone_aware() -> None:
    assert make_task().created_at.tzinfo is not None


def test_task_rejects_naive_datetime() -> None:
    with pytest.raises(ValidationError):
        TaskRequest.model_validate({"description": "x", "created_at": datetime(2026, 1, 1)})


@pytest.mark.parametrize("value", [0, -1])
def test_task_rejects_non_positive_max_iterations(value: int) -> None:
    with pytest.raises(ValidationError):
        TaskRequest(description="x", max_iterations=value)


def test_task_rejects_empty_description() -> None:
    with pytest.raises(ValidationError):
        TaskRequest(description="  ")


def test_spec_json_round_trip() -> None:
    spec = make_spec()
    assert ScientificSpecification.model_validate_json(spec.model_dump_json()) == spec


def test_spec_requires_at_least_one_success_criterion() -> None:
    data = make_spec().model_dump()
    data["success_criteria"] = []
    with pytest.raises(ValidationError):
        ScientificSpecification.model_validate(data)


def test_spec_rejects_unknown_comparison_operator() -> None:
    data = make_spec().model_dump()
    data["success_criteria"][0]["op"] = "=="
    with pytest.raises(ValidationError):
        ScientificSpecification.model_validate(data)


def test_spec_parameters_are_scalars_only() -> None:
    data = make_spec().model_dump()
    data["parameters"]["coupling_matrix"] = [[0.0, 1.0], [1.0, 0.0]]
    with pytest.raises(ValidationError):
        ScientificSpecification.model_validate(data)


def test_spec_task_type_is_extensible() -> None:
    data = make_spec().model_dump()
    data["task_type"] = "reservoir_computing"  # not in any hard-coded list
    assert ScientificSpecification.model_validate(data).task_type == "reservoir_computing"
