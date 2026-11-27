"""Safety Validator: deterministic check of every device command against the registry.

The Runner LLM only *proposes* commands. Nothing reaches a backend unless this code
accepts it. Out-of-range values are rejected and reported, never clamped.
"""

import math
from collections.abc import Sequence

from experimental_system.devices.registry import DeviceRegistry
from experimental_system.schemas.common import ScalarValue
from experimental_system.schemas.devices import (
    DeviceCommand,
    ParameterSpec,
    ValidationResult,
    Violation,
)


def check_value(spec: ParameterSpec, value: ScalarValue, unit: str | None) -> list[Violation]:
    """Violations of one parameter value (empty list = valid).

    Type rules are strict on purpose: ``bool`` is never accepted as a number, and a float
    such as ``5.0`` is not accepted for an ``int`` parameter.
    """
    name = spec.name
    if unit != spec.unit:
        return [
            Violation(
                code="wrong_unit",
                parameter=name,
                message=f"{name}: unit {unit!r} given, registry requires {spec.unit!r}",
            )
        ]

    if spec.kind == "bool":
        if not isinstance(value, bool):
            return [_wrong_type(name, "bool", value)]
        return []

    if spec.kind == "choice":
        if not isinstance(value, str):
            return [_wrong_type(name, "string choice", value)]
        if spec.choices is not None and value not in spec.choices:
            return [
                Violation(
                    code="out_of_range",
                    parameter=name,
                    message=f"{name}: {value!r} is not one of {spec.choices}",
                )
            ]
        return []

    # Numeric kinds.
    if isinstance(value, bool) or not isinstance(value, int | float):
        return [_wrong_type(name, spec.kind, value)]
    if spec.kind == "int" and not isinstance(value, int):
        return [_wrong_type(name, "int", value)]
    number = float(value)
    if not math.isfinite(number):
        return [Violation(code="out_of_range", parameter=name, message=f"{name}: not finite")]
    if spec.minimum is not None and number < spec.minimum:
        return [_out_of_range(spec, value)]
    if spec.maximum is not None and number > spec.maximum:
        return [_out_of_range(spec, value)]
    return []


class SafetyValidator:
    """Checks commands against a DeviceRegistry. Stateless apart from the registry."""

    def __init__(self, registry: DeviceRegistry) -> None:
        self._registry = registry

    def validate(self, command: DeviceCommand) -> ValidationResult:
        """Check one command; ``result.accepted`` is True iff there are no violations."""
        device = self._registry.get_device(command.device_id)
        if device is None:
            return _reject(command, "unknown_device", f"device {command.device_id!r} not found")
        operation = device.operation(command.operation)
        if operation is None:
            known = [o.name for o in device.operations]
            return _reject(
                command,
                "unknown_operation",
                f"device {command.device_id!r} has no operation {command.operation!r}; "
                f"known: {known}",
            )

        violations: list[Violation] = []
        for name in command.parameters:
            if operation.parameter(name) is None:
                violations.append(
                    Violation(
                        code="unknown_parameter",
                        parameter=name,
                        message=f"operation {operation.name!r} has no parameter {name!r}",
                    )
                )
        for spec in operation.parameters:
            given = command.parameters.get(spec.name)
            if given is None:
                if spec.required:
                    violations.append(
                        Violation(
                            code="missing_parameter",
                            parameter=spec.name,
                            message=f"required parameter {spec.name!r} is missing",
                        )
                    )
                continue
            violations.extend(check_value(spec, given.value, given.unit))
        return ValidationResult(command=command, violations=violations)

    def validate_batch(self, commands: Sequence[DeviceCommand]) -> list[ValidationResult]:
        """Check every command independently (all problems are reported at once)."""
        return [self.validate(c) for c in commands]


def all_accepted(results: Sequence[ValidationResult]) -> bool:
    """True iff every result is accepted (and there is at least one)."""
    return bool(results) and all(r.accepted for r in results)


def _reject(command: DeviceCommand, code: str, message: str) -> ValidationResult:
    violation = Violation.model_validate({"code": code, "message": message})
    return ValidationResult(command=command, violations=[violation])


def _wrong_type(name: str, expected: str, value: object) -> Violation:
    return Violation(
        code="wrong_type",
        parameter=name,
        message=f"{name}: expected {expected}, got {type(value).__name__} {value!r}",
    )


def _out_of_range(spec: ParameterSpec, value: ScalarValue) -> Violation:
    unit = f" {spec.unit}" if spec.unit else ""
    return Violation(
        code="out_of_range",
        parameter=spec.name,
        message=(
            f"{spec.name}: {value}{unit} is outside the allowed range "
            f"[{spec.minimum}, {spec.maximum}]{unit}"
        ),
    )
