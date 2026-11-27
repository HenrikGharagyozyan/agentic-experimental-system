"""Helpers to build device commands concisely in tests."""

from experimental_system.schemas import CommandParam, DeviceCommand, ScalarValue

Param = ScalarValue | tuple[ScalarValue, str]


def cmd(device: str, operation: str, step: str = "s1", **params: Param) -> DeviceCommand:
    """``cmd("sim_laser", "set_power", power=(10.0, "mW"))``; bare values have no unit."""
    parameters = {}
    for name, value in params.items():
        if isinstance(value, tuple):
            parameters[name] = CommandParam(value=value[0], unit=value[1])
        else:
            parameters[name] = CommandParam(value=value)
    return DeviceCommand(step_id=step, device_id=device, operation=operation, parameters=parameters)


LASER_ON = [
    cmd("sim_laser", "set_power", step="s0", power=(10.0, "mW")),
    cmd("sim_laser", "set_emission", step="s0", enabled=True),
]
