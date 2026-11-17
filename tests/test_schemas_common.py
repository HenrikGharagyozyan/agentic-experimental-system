"""Shared contract behaviour: identifiers, strictness, immutability, computed fields."""

import pytest
from pydantic import ValidationError

from experimental_system.schemas import (
    Contract,
    Identifier,
    NonEmptyStr,
    ScalarValue,
    ValidationResult,
    Violation,
)
from factories import make_command


class _Sample(Contract):
    ident: Identifier
    text: NonEmptyStr = "x"
    scalar: ScalarValue = 0


@pytest.mark.parametrize("value", ["slm_main", "s1", "a", "camera_2"])
def test_identifier_accepts_snake_case(value: str) -> None:
    assert _Sample(ident=value).ident == value


@pytest.mark.parametrize("value", ["SLM #1", "1abc", "", "has-dash", "Upper", "a" * 65])
def test_identifier_rejects_invalid(value: str) -> None:
    with pytest.raises(ValidationError):
        _Sample(ident=value)


def test_non_empty_str_rejects_whitespace() -> None:
    with pytest.raises(ValidationError):
        _Sample(ident="ok", text="   ")


@pytest.mark.parametrize(("value", "expected_type"), [(True, bool), (1, int), (1.5, float)])
def test_scalar_value_keeps_exact_type(value: ScalarValue, expected_type: type) -> None:
    assert type(_Sample(ident="ok", scalar=value).scalar) is expected_type


def test_extra_fields_are_forbidden() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        _Sample.model_validate({"ident": "ok", "hallucinated": 1})


def test_contracts_are_frozen() -> None:
    sample = _Sample(ident="ok")
    with pytest.raises(ValidationError):
        sample.ident = "other"  # type: ignore[misc]


def test_model_copy_produces_updated_copy() -> None:
    sample = _Sample(ident="ok")
    updated = sample.model_copy(update={"ident": "new"})
    assert (sample.ident, updated.ident) == ("ok", "new")


def test_computed_field_round_trip() -> None:
    result = ValidationResult(command=make_command())
    dumped = result.model_dump_json()
    assert '"accepted":true' in dumped
    assert ValidationResult.model_validate_json(dumped) == result


def test_forged_computed_value_is_ignored() -> None:
    data = ValidationResult(
        command=make_command(),
        violations=[Violation(code="out_of_range", parameter="level", message="too high")],
    ).model_dump()
    data["accepted"] = True  # forged
    assert ValidationResult.model_validate(data).accepted is False
