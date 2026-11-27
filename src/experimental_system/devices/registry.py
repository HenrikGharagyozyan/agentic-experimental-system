"""Device Registry interface: the only source of device facts."""

from typing import Protocol, runtime_checkable

from experimental_system.schemas.common import ScalarValue
from experimental_system.schemas.devices import DeviceSpec, ParameterSpec


@runtime_checkable
class DeviceRegistry(Protocol):
    """Read-only access to human-verified device descriptions.

    Device parameters, ranges, units and capabilities come only from here, never from
    the Knowledge Base or from an LLM's memory.
    """

    def list_devices(self) -> list[DeviceSpec]:
        """All registered devices."""
        ...

    def get_device(self, device_id: str) -> DeviceSpec | None:
        """The device with this id, or None if it is not registered."""
        ...


def operation_defaults(
    registry: DeviceRegistry, device_id: str, operation: str
) -> dict[str, ScalarValue]:
    """Defaults of the optional parameters of one operation (unknown op -> {})."""
    device = registry.get_device(device_id)
    op = device.operation(operation) if device else None
    if op is None:
        return {}
    return {p.name: p.default for p in op.parameters if p.default is not None}


def parameter_spec(
    registry: DeviceRegistry, device_id: str, operation: str, parameter: str
) -> ParameterSpec | None:
    """Spec of one parameter, or None if any part is unknown."""
    device = registry.get_device(device_id)
    op = device.operation(operation) if device else None
    return op.parameter(parameter) if op else None
