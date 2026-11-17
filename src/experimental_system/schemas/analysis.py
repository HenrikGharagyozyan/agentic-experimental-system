"""Metrics (computed in code) and the Analyst's report (produced by an LLM)."""

from enum import StrEnum
from typing import Self

from pydantic import Field, FiniteFloat, computed_field, model_validator

from experimental_system.schemas.common import Contract, Identifier, NonEmptyStr
from experimental_system.schemas.task import SuccessCriterion


class CriterionResult(Contract):
    """Deterministic evaluation of one success criterion."""

    criterion: SuccessCriterion
    observed: float | None  # None: the metric was not produced -> criterion fails
    passed: bool


class Metrics(Contract):
    """Numbers computed by scientific_core. Never produced by an LLM."""

    values: dict[Identifier, FiniteFloat] = Field(default_factory=dict)
    criteria: list[CriterionResult] = Field(default_factory=list)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def all_criteria_met(self) -> bool:
        """True only if there is at least one criterion and every criterion passed."""
        return bool(self.criteria) and all(c.passed for c in self.criteria)


class Decision(StrEnum):
    DONE = "DONE"  # success criteria met, finish
    REPLAN = "REPLAN"  # adjust the experiment plan -> Experiment agent
    REMODEL = "REMODEL"  # rethink the scientific model -> Scientist agent
    ABORT = "ABORT"  # stop with an error


class AnalysisReport(Contract):
    """Output of the Analyst agent: interpretation and routing decision."""

    decision: Decision
    rationale: NonEmptyStr
    anomalies: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    referenced_metrics: list[Identifier] = Field(default_factory=list)
    # TODO(later, orchestrator): check that every referenced_metrics name exists in
    # Metrics.values; this needs Metrics, so it cannot be validated inside this schema.
    # TODO(later, orchestrator): decide what to do when decision == DONE but
    # Metrics.all_criteria_met is False (never finish as DONE in that case).

    @model_validator(mode="after")
    def _check_recommendations(self) -> Self:
        if self.decision in (Decision.REPLAN, Decision.REMODEL) and not self.recommendations:
            raise ValueError(f"decision {self.decision} requires at least one recommendation")
        return self
