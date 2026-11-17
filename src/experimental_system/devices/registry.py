"""Device Registry interface: the only source of device facts."""

from typing import Protocol, runtime_checkable

from experimental_system.schemas.devices import DeviceSpec


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
