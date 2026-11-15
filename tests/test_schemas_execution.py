"""ExecutionResult and related schemas."""

from datetime import datetime, timedelta

import pytest
from pydantic import ValidationError

from experimental_system.schemas import ExecutionResult, ExecutionStatus
from factories import T0, make_execution


def test_execution_round_trip() -> None:
    result = make_execution()
    assert ExecutionResult.model_validate_json(result.model_dump_json()) == result


def test_execution_rejects_finish_before_start() -> None:
    data = make_execution().model_dump()
    data["finished_at"] = T0 - timedelta(seconds=1)
    with pytest.raises(ValidationError, match="earlier than started_at"):
        ExecutionResult.model_validate(data)


def test_success_with_errors_is_rejected() -> None:
    data = make_execution().model_dump()
    data["errors"] = [{"message": "detector timeout"}]
    with pytest.raises(ValidationError, match="SUCCESS is not allowed"):
        ExecutionResult.model_validate(data)


def test_partial_with_errors_is_allowed() -> None:
    data = make_execution().model_dump()
    data["status"] = ExecutionStatus.PARTIAL
    data["errors"] = [{"message": "detector timeout"}]
    assert ExecutionResult.model_validate(data).status is ExecutionStatus.PARTIAL


def test_execution_rejects_naive_datetimes() -> None:
    data = make_execution().model_dump()
    data["started_at"] = datetime(2026, 1, 1)
    with pytest.raises(ValidationError):
        ExecutionResult.model_validate(data)


def test_device_status_rejects_unknown_state() -> None:
    data = make_execution().model_dump()
    data["device_statuses"][0]["state"] = "on_fire"
    with pytest.raises(ValidationError):
        ExecutionResult.model_validate(data)
