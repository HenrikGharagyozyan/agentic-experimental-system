"""Shared experiment state driven by the orchestrator."""

from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from experimental_system.schemas.analysis import AnalysisReport, Metrics
from experimental_system.schemas.common import Contract, new_id
from experimental_system.schemas.devices import DeviceCommand, ValidationResult
from experimental_system.schemas.execution import ExecutionResult
from experimental_system.schemas.plan import ExperimentPlan
from experimental_system.schemas.task import ScientificSpecification, TaskRequest


class ExperimentStatus(StrEnum):
    RUNNING = "RUNNING"
    DONE = "DONE"
    ABORTED = "ABORTED"  # Analyst decided ABORT
    ITERATION_LIMIT = "ITERATION_LIMIT"  # max_iterations reached without success
    FAILED = "FAILED"  # technical error (backend, LLM, validation)


class IterationRecord(Contract):
    """Snapshot of one full cycle, appended to the history."""

    iteration: int = Field(ge=0)
    specification: ScientificSpecification
    plan: ExperimentPlan | None = None
    validations: list[ValidationResult] = Field(default_factory=list)
    execution: ExecutionResult | None = None
    metrics: Metrics | None = None
    analysis: AnalysisReport | None = None


class ExperimentState(Contract):
    """Everything the orchestrator knows about one experiment run."""

    experiment_id: str = Field(default_factory=new_id)
    task: TaskRequest
    status: ExperimentStatus = ExperimentStatus.RUNNING
    iteration: int = Field(default=0, ge=0)
    max_iterations: int = Field(gt=0)

    # Current iteration
    specification: ScientificSpecification | None = None
    plan: ExperimentPlan | None = None
    commands: list[DeviceCommand] = Field(default_factory=list)
    validations: list[ValidationResult] = Field(default_factory=list)
    execution: ExecutionResult | None = None
    metrics: Metrics | None = None
    analysis: AnalysisReport | None = None

    history: list[IterationRecord] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_iteration_limit(self) -> Self:
        if self.iteration > self.max_iterations:
            raise ValueError(
                f"iteration {self.iteration} exceeds max_iterations {self.max_iterations}"
            )
        return self
