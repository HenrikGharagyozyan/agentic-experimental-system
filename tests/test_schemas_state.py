"""ExperimentState and IterationRecord."""

import pytest
from pydantic import ValidationError

from experimental_system.schemas import (
    ExperimentState,
    ExperimentStatus,
    TaskRequest,
    new_id,
    utc_now,
)
from factories import make_state, make_task


def test_new_state_defaults() -> None:
    state = ExperimentState(task=make_task(), max_iterations=3)
    assert state.status is ExperimentStatus.RUNNING
    assert state.iteration == 0
    assert state.history == []


def test_each_state_gets_a_unique_experiment_id() -> None:
    first = ExperimentState(task=make_task(), max_iterations=3)
    second = ExperimentState(task=make_task(), max_iterations=3)
    assert first.experiment_id != second.experiment_id


def test_ids_and_timestamps_use_default_factory() -> None:
    # A factory is called per object; a plain default would be computed once at import.
    assert ExperimentState.model_fields["experiment_id"].default_factory is new_id
    assert TaskRequest.model_fields["created_at"].default_factory is utc_now


def test_iteration_cannot_exceed_max_iterations() -> None:
    with pytest.raises(ValidationError, match="exceeds max_iterations"):
        ExperimentState(task=make_task(), iteration=4, max_iterations=3)


def test_max_iterations_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        ExperimentState(task=make_task(), max_iterations=0)


def test_full_state_json_round_trip() -> None:
    state = make_state()
    restored = ExperimentState.model_validate_json(state.model_dump_json())
    assert restored == state
    assert restored.validations[0].accepted is True
    assert restored.metrics is not None and restored.metrics.all_criteria_met is True


def test_state_update_via_model_copy() -> None:
    state = make_state()
    finished = state.model_copy(update={"status": ExperimentStatus.DONE})
    assert state.status is ExperimentStatus.RUNNING
    assert finished.status is ExperimentStatus.DONE
    assert finished.experiment_id == state.experiment_id
