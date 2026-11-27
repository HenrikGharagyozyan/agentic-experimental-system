"""Results returned by an execution backend."""

from enum import StrEnum
from typing import Literal, Self

from pydantic import AwareDatetime, Field, model_validator

from experimental_system.schemas.common import Contract, Identifier, NonEmptyStr


class Measurement(Contract):
    """A scalar measurement. Large data (frames, masks) is referenced, never inlined."""

    name: Identifier
    value: float
    unit: str | None = None
    step_id: Identifier | None = None
    device_id: Identifier | None = None
    # Position of the producing command in the executed batch: several commands may share
    # one step_id, so derived metrics group measurements by command, not by step.
    command_index: int | None = Field(default=None, ge=0)
    # Opaque reference to large array data held by Storage (camera frames, SLM masks,
    # matrices), e.g. "arrays/it01_0003_s1_tm_estimate.npy". LLMs never see raw arrays.
    data_ref: str | None = None


DeviceState = Literal["ok", "busy", "error", "offline"]


class DeviceStatus(Contract):
    """Health/availability of one device as reported by the backend."""

    device_id: Identifier
    state: DeviceState
    message: str | None = None


class ExecutionError(Contract):
    """An error that occurred while executing commands."""

    message: NonEmptyStr
    step_id: Identifier | None = None
    device_id: Identifier | None = None


class ExecutionStatus(StrEnum):
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class ExecutionResult(Contract):
    """Raw outcome of executing a batch of validated commands."""

    backend: NonEmptyStr  # e.g. "simulation"; recorded for reproducibility
    status: ExecutionStatus
    measurements: list[Measurement] = Field(default_factory=list)
    device_statuses: list[DeviceStatus] = Field(default_factory=list)
    errors: list[ExecutionError] = Field(default_factory=list)
    started_at: AwareDatetime
    finished_at: AwareDatetime

    @model_validator(mode="after")
    def _check_consistency(self) -> Self:
        if self.finished_at < self.started_at:
            raise ValueError("finished_at is earlier than started_at")
        if self.status is ExecutionStatus.SUCCESS and self.errors:
            raise ValueError("status SUCCESS is not allowed when errors are present")
        return self
