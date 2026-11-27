"""Device Registry content, device commands and Safety Validator results."""

from typing import Literal, Self

from pydantic import Field, computed_field, model_validator

from experimental_system.schemas.common import Contract, Identifier, NonEmptyStr, ScalarValue

# --- Registry content (human-verified config, never produced by an LLM) -------------------

ParameterKind = Literal["float", "int", "bool", "choice"]


class ParameterSpec(Contract):
    """Allowed values of one operation parameter."""

    name: Identifier
    kind: ParameterKind
    unit: str | None = None
    minimum: float | None = None
    maximum: float | None = None
    choices: list[str] | None = None
    required: bool = True
    # Value the backend uses when an optional parameter is omitted. Checked against this
    # spec when the registry is loaded (devices.yaml_registry).
    default: ScalarValue | None = None
    description: str = ""

    @model_validator(mode="after")
    def _check_consistency(self) -> Self:
        if self.required and self.default is not None:
            raise ValueError(f"parameter {self.name!r}: a required parameter has no default")
        numeric = self.kind in ("float", "int")
        has_range = self.minimum is not None or self.maximum is not None
        if has_range and not numeric:
            raise ValueError(f"parameter {self.name!r}: range is only allowed for float/int")
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError(f"parameter {self.name!r}: minimum > maximum")
        if self.kind == "choice" and not self.choices:
            raise ValueError(f"parameter {self.name!r}: kind 'choice' requires choices")
        if self.kind != "choice" and self.choices is not None:
            raise ValueError(f"parameter {self.name!r}: choices are only allowed for 'choice'")
        return self


class OperationSpec(Contract):
    """An operation a device supports, with its parameters."""

    name: Identifier
    description: str = ""
    parameters: list[ParameterSpec] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_unique_parameters(self) -> Self:
        _require_unique([p.name for p in self.parameters], f"operation {self.name!r} parameter")
        return self

    def parameter(self, name: str) -> ParameterSpec | None:
        """The parameter with this name, or None."""
        return next((p for p in self.parameters if p.name == name), None)


class DeviceSpec(Contract):
    """A device as described in the Device Registry."""

    device_id: Identifier
    kind: Identifier  # free id ("slm", "camera", ...), not a closed enum
    description: str = ""
    operations: list[OperationSpec] = Field(min_length=1)
    # TODO(later): settle_time, dependencies between devices.

    @model_validator(mode="after")
    def _check_unique_operations(self) -> Self:
        _require_unique([o.name for o in self.operations], f"device {self.device_id!r} operation")
        return self

    def operation(self, name: str) -> OperationSpec | None:
        """The operation with this name, or None."""
        return next((o for o in self.operations if o.name == name), None)


class RegistryDocument(Contract):
    """Top-level content of a registry config file (e.g. configs/devices/simulation.yaml)."""

    name: Identifier
    simulation_only: bool  # True: fictional values, never valid for real hardware
    notice: str = ""
    devices: list[DeviceSpec] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_unique_devices(self) -> Self:
        _require_unique([d.device_id for d in self.devices], "device_id")
        return self


def _require_unique(names: list[str], what: str) -> None:
    seen: set[str] = set()
    for name in names:
        if name in seen:
            raise ValueError(f"duplicate {what}: {name!r}")
        seen.add(name)


# --- Commands (proposed by the Runner LLM) -------------------------------------------------


class CommandParam(Contract):
    """Parameter value with an explicit unit.

    The unit must match the registry exactly; the Safety Validator never converts units.
    """

    value: ScalarValue
    unit: str | None = None


class DeviceCommand(Contract):
    """One concrete device command implementing (part of) a plan step."""

    step_id: Identifier
    device_id: Identifier
    operation: Identifier
    parameters: dict[Identifier, CommandParam] = Field(default_factory=dict)


class CommandBatch(Contract):
    """Output of the Runner agent: commands to validate and execute."""

    commands: list[DeviceCommand] = Field(min_length=1)


# --- Safety Validator output (deterministic code) ------------------------------------------

ViolationCode = Literal[
    "unknown_device",
    "unknown_operation",
    "unknown_parameter",
    "missing_parameter",
    "wrong_type",
    "wrong_unit",
    "out_of_range",
]


class Violation(Contract):
    """Why a command was rejected."""

    code: ViolationCode
    parameter: str | None = None
    message: NonEmptyStr


class ValidationResult(Contract):
    """Result of checking one command against the Device Registry."""

    command: DeviceCommand
    violations: list[Violation] = Field(default_factory=list)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def accepted(self) -> bool:
        """Derived, never set directly: a command is accepted iff it has no violations."""
        return not self.violations
