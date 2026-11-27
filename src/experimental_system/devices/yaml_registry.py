"""Device Registry loaded from a human-verified YAML file."""

from pathlib import Path

import yaml

from experimental_system.devices.registry import operation_defaults
from experimental_system.devices.validator import check_value
from experimental_system.schemas.common import ScalarValue
from experimental_system.schemas.devices import DeviceSpec, RegistryDocument


class RegistryError(ValueError):
    """The registry file is missing or inconsistent."""


class YamlDeviceRegistry:
    """Implements the ``DeviceRegistry`` protocol from a ``RegistryDocument``.

    On construction every parameter default is checked against its own spec, so a broken
    config fails at startup, not in the middle of an experiment.
    """

    def __init__(self, document: RegistryDocument) -> None:
        self._document = document
        self._devices = {d.device_id: d for d in document.devices}
        for device in document.devices:
            for operation in device.operations:
                for spec in operation.parameters:
                    if spec.default is None:
                        continue
                    problems = check_value(spec, spec.default, spec.unit)
                    if problems:
                        raise RegistryError(
                            f"{device.device_id}.{operation.name}: invalid default: "
                            f"{problems[0].message}"
                        )

    @classmethod
    def from_file(cls, path: Path) -> "YamlDeviceRegistry":
        if not path.is_file():
            raise RegistryError(f"registry file not found: {path}")
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return cls(RegistryDocument.model_validate(data))

    @property
    def document(self) -> RegistryDocument:
        return self._document

    @property
    def simulation_only(self) -> bool:
        return self._document.simulation_only

    def list_devices(self) -> list[DeviceSpec]:
        return list(self._devices.values())

    def get_device(self, device_id: str) -> DeviceSpec | None:
        return self._devices.get(device_id)

    def defaults(self, device_id: str, operation: str) -> dict[str, ScalarValue]:
        """Defaults of the optional parameters of one operation (unknown op -> {})."""
        return operation_defaults(self, device_id, operation)
