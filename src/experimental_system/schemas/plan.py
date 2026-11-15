"""Step-level experiment plan produced by the Experiment agent."""

from typing import Self

from pydantic import Field, model_validator

from experimental_system.schemas.common import Contract, Identifier, NonEmptyStr, ScalarValue


class PlanStep(Contract):
    """One step at the level of "what to do" (not concrete device commands)."""

    step_id: Identifier  # e.g. "s1"; unique within a plan
    action: Identifier  # extensible, e.g. "calibrate_transmission_matrix", "capture"
    description: NonEmptyStr
    devices: list[Identifier] = Field(default_factory=list)  # checked against registry later
    parameters: dict[str, ScalarValue] = Field(default_factory=dict)
    depends_on: list[Identifier] = Field(default_factory=list)


class ExperimentPlan(Contract):
    """Output of the Experiment agent: ordered steps to execute."""

    rationale: NonEmptyStr
    steps: list[PlanStep] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_step_ids_and_dependencies(self) -> Self:
        seen: set[str] = set()
        for step in self.steps:
            if step.step_id in seen:
                raise ValueError(f"duplicate step_id: {step.step_id!r}")
            for dep in step.depends_on:
                if dep not in seen:
                    raise ValueError(
                        f"step {step.step_id!r} depends on {dep!r}, "
                        "which is not an earlier step in the plan"
                    )
            seen.add(step.step_id)
        return self
