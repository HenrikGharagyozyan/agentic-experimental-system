"""Task input and the Scientist's scientific specification."""

from typing import Literal

from pydantic import AwareDatetime, Field

from experimental_system.schemas.common import (
    Contract,
    Identifier,
    NonEmptyStr,
    ScalarValue,
    utc_now,
)


class TaskRequest(Contract):
    """A scientific task as submitted by a human (or later an API)."""

    description: NonEmptyStr
    task_type_hint: Identifier | None = None
    constraints: dict[str, ScalarValue] = Field(default_factory=dict)
    # None means "use the default from settings" (resolved by the orchestrator).
    max_iterations: int | None = Field(default=None, gt=0)
    created_at: AwareDatetime = Field(default_factory=utc_now)


class Citation(Contract):
    """Reference to a knowledge card the Scientist relied on (checked in code)."""

    card_id: Identifier
    note: str | None = None


class MathModel(Contract):
    """Mathematical model of the problem. Equations are text, never evaluated by an LLM."""

    description: NonEmptyStr
    equations: list[str] = Field(default_factory=list)  # LaTeX or plain text
    variables: dict[str, str] = Field(default_factory=dict)  # symbol -> meaning


class SuccessCriterion(Contract):
    """Machine-checkable criterion: ``Metrics.values[metric] <op> target``."""

    metric: Identifier
    op: Literal["<", "<=", ">", ">="]
    target: float
    description: str | None = None


class ScientificSpecification(Contract):
    """Output of the Scientist agent: what the problem is and how success is measured."""

    objective: NonEmptyStr
    task_type: Identifier  # extensible: any snake_case id, not a closed enum
    math_model: MathModel
    # Problem parameters (e.g. n_spins), NOT device parameters. Scalars only.
    # TODO(later): matrices (J, transmission matrix) are passed by reference (data_ref),
    # never inline — added together with Storage.
    parameters: dict[str, ScalarValue] = Field(default_factory=dict)
    success_criteria: list[SuccessCriterion] = Field(min_length=1)
    assumptions: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
