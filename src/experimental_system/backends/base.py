"""Execution backend interface shared by the simulation and (later) hardware backends."""

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from experimental_system.schemas.devices import DeviceCommand
from experimental_system.schemas.execution import DeviceStatus, ExecutionResult


@runtime_checkable
class ExecutionBackend(Protocol):
    """Executes device commands. Agents never know which implementation is active.

    Contract: callers (the orchestrator) pass only commands already accepted by the
    Safety Validator.
    TODO(later): the hardware backend must ALWAYS re-validate every command through the
    Safety Validator itself before it reaches a device (defense in depth).
    """

    @property
    def name(self) -> str:
        """Backend identifier recorded in ExecutionResult.backend (e.g. "simulation")."""
        ...

    def device_status(self, device_ids: Sequence[str] | None = None) -> list[DeviceStatus]:
        """Health/availability of the given devices (all devices if None)."""
        ...

    def execute(self, commands: Sequence[DeviceCommand]) -> ExecutionResult:
        """Execute validated commands in order and return raw measurements."""
        ...
