"""Device Registry content, commands and validation results."""

from typing import Any

import pytest
from pydantic import ValidationError

from experimental_system.schemas import (
    CommandBatch,
    DeviceSpec,
    ParameterSpec,
    ValidationResult,
    Violation,
)
from factories import make_command, make_device


def test_device_spec_round_trip() -> None:
    device = make_device()
    assert DeviceSpec.model_validate_json(device.model_dump_json()) == device


def test_device_requires_operations() -> None:
    with pytest.raises(ValidationError):
        DeviceSpec(device_id="test_source", kind="source", operations=[])


@pytest.mark.parametrize(
    ("spec", "message"),
    [
        ({"name": "p", "kind": "float", "minimum": 10, "maximum": 1}, "minimum > maximum"),
        ({"name": "p", "kind": "choice"}, "requires choices"),
        ({"name": "p", "kind": "bool", "maximum": 1}, "range is only allowed"),
        ({"name": "p", "kind": "float", "choices": ["a"]}, "choices are only allowed"),
    ],
)
def test_parameter_spec_rejects_inconsistent_definitions(
    spec: dict[str, Any], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        ParameterSpec.model_validate(spec)


def test_parameter_spec_accepts_equal_bounds() -> None:
    assert ParameterSpec(name="p", kind="int", minimum=3, maximum=3).maximum == 3


def test_command_keeps_explicit_units() -> None:
    assert make_command().parameters["level"].unit == "mV"


def test_command_batch_requires_commands() -> None:
    with pytest.raises(ValidationError):
        CommandBatch(commands=[])


def test_validation_result_accepted_without_violations() -> None:
    assert ValidationResult(command=make_command()).accepted is True


def test_validation_result_rejected_with_violations() -> None:
    result = ValidationResult(
        command=make_command(),
        violations=[Violation(code="wrong_unit", parameter="level", message="expected mV")],
    )
    assert result.accepted is False


def test_violation_rejects_unknown_code() -> None:
    with pytest.raises(ValidationError):
        Violation.model_validate({"code": "looks_fine", "message": "x"})
