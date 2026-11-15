"""Shared building blocks for all inter-component contracts."""

from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

# snake_case identifier used for device ids, operations, step ids, metric names, task types.
# Keeps LLM output machine-friendly: "slm_main" is valid, "SLM #1" is rejected.
Identifier = Annotated[
    str,
    StringConstraints(pattern=r"^[a-z][a-z0-9_]*$", max_length=64),
]

# Free text that must not be empty or whitespace-only.
NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

# JSON scalar. Pydantic's "smart" union mode keeps the exact input type
# (True stays bool, 1 stays int, 1.5 stays float).
ScalarValue = bool | int | float | str


class Contract(BaseModel):
    """Base class for every contract exchanged between components.

    - ``extra="forbid"``: unknown fields (e.g. hallucinated by an LLM) are a validation
      error, not silently dropped.
    - ``frozen=True``: instances are immutable; produce updated copies with
      ``model_copy(update=...)``.
    - Computed fields (``@computed_field``) are included in serialized output but are
      always re-derived from data: on input they are dropped, so a dumped object can be
      loaded back (round-trip) and a stale/forged derived value is never trusted.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="before")
    @classmethod
    def _drop_computed_fields(cls, data: Any) -> Any:
        if isinstance(data, dict) and cls.model_computed_fields:
            return {k: v for k, v in data.items() if k not in cls.model_computed_fields}
        return data


def utc_now() -> datetime:
    """Current time as a timezone-aware UTC datetime."""
    return datetime.now(UTC)


def new_id() -> str:
    """Random unique id (32 hex characters)."""
    return uuid4().hex
