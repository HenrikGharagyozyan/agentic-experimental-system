"""Safety Validator: every violation code, strict types, no clamping."""

import math

import pytest

from experimental_system.devices import SafetyValidator, YamlDeviceRegistry, all_accepted
from experimental_system.schemas import CommandParam, DeviceCommand, ScalarValue


def _cmd(device: str, op: str, **params: tuple[ScalarValue, str | None]) -> DeviceCommand:
    return DeviceCommand(
        step_id="s1",
        device_id=device,
        operation=op,
        parameters={k: CommandParam(value=v, unit=u) for k, (v, u) in params.items()},
    )


@pytest.fixture
def validator(sim_registry: YamlDeviceRegistry) -> SafetyValidator:
    return SafetyValidator(sim_registry)


def _codes(validator: SafetyValidator, command: DeviceCommand) -> list[str]:
    return [v.code for v in validator.validate(command).violations]


def test_valid_command_accepted(validator: SafetyValidator) -> None:
    result = validator.validate(_cmd("sim_laser", "set_power", power=(10.0, "mW")))
    assert result.accepted


def test_int_accepted_for_float(validator: SafetyValidator) -> None:
    assert validator.validate(_cmd("sim_laser", "set_power", power=(10, "mW"))).accepted


def test_boundaries_inclusive(validator: SafetyValidator) -> None:
    assert validator.validate(_cmd("sim_laser", "set_power", power=(50.0, "mW"))).accepted
    assert validator.validate(_cmd("sim_laser", "set_power", power=(0.0, "mW"))).accepted


def test_out_of_range_rejected_not_clamped(validator: SafetyValidator) -> None:
    command = _cmd("sim_laser", "set_power", power=(500.0, "mW"))
    result = validator.validate(command)
    assert not result.accepted
    assert [v.code for v in result.violations] == ["out_of_range"]
    assert result.command.parameters["power"].value == 500.0  # unchanged


def test_unknown_device(validator: SafetyValidator) -> None:
    assert _codes(validator, _cmd("laser_x", "set_power")) == ["unknown_device"]


def test_unknown_operation(validator: SafetyValidator) -> None:
    assert _codes(validator, _cmd("sim_laser", "explode")) == ["unknown_operation"]


def test_unknown_and_missing_parameter(validator: SafetyValidator) -> None:
    codes = _codes(validator, _cmd("sim_laser", "set_power", watts=(1.0, "mW")))
    assert sorted(codes) == ["missing_parameter", "unknown_parameter"]


def test_wrong_unit(validator: SafetyValidator) -> None:
    assert _codes(validator, _cmd("sim_laser", "set_power", power=(0.01, "W"))) == ["wrong_unit"]


def test_missing_unit(validator: SafetyValidator) -> None:
    assert _codes(validator, _cmd("sim_laser", "set_power", power=(1.0, None))) == ["wrong_unit"]


@pytest.mark.parametrize("value", [True, "10", None])
def test_wrong_type_for_float(validator: SafetyValidator, value: ScalarValue) -> None:
    command = DeviceCommand.model_validate(
        {
            "step_id": "s1",
            "device_id": "sim_laser",
            "operation": "set_power",
            "parameters": {"power": {"value": value, "unit": "mW"}} if value is not None else {},
        }
    )
    expected = ["missing_parameter"] if value is None else ["wrong_type"]
    assert _codes(validator, command) == expected


def test_float_not_accepted_for_int(validator: SafetyValidator) -> None:
    assert _codes(validator, _cmd("sim_slm", "configure", grid_side=(4.0, None))) == ["wrong_type"]


def test_int_parameter_range(validator: SafetyValidator) -> None:
    assert validator.validate(_cmd("sim_slm", "configure", grid_side=(16, None))).accepted
    assert _codes(validator, _cmd("sim_slm", "configure", grid_side=(17, None))) == ["out_of_range"]


def test_non_finite_rejected(validator: SafetyValidator) -> None:
    for value in (math.nan, math.inf):
        assert _codes(validator, _cmd("sim_laser", "set_power", power=(value, "mW"))) == [
            "out_of_range"
        ]


def test_bool_parameter(validator: SafetyValidator) -> None:
    assert validator.validate(_cmd("sim_laser", "set_emission", enabled=(True, None))).accepted
    assert _codes(validator, _cmd("sim_laser", "set_emission", enabled=(1, None))) == ["wrong_type"]


def test_choice_parameter(validator: SafetyValidator) -> None:
    ok = _cmd(
        "procedures",
        "calibrate_transmission_matrix",
        gamma=(4.0, None),
        algorithm=("ggs_1", None),
    )
    assert validator.validate(ok).accepted
    bad = _cmd(
        "procedures", "calibrate_transmission_matrix", gamma=(4.0, None), algorithm=("ggs_9", None)
    )
    assert _codes(validator, bad) == ["out_of_range"]


def test_optional_parameters_may_be_omitted(validator: SafetyValidator) -> None:
    command = _cmd("procedures", "calibrate_transmission_matrix", gamma=(4.0, None))
    assert validator.validate(command).accepted


def test_procedure_parameter_out_of_range(validator: SafetyValidator) -> None:
    command = _cmd(
        "procedures",
        "run_ising_optimization",
        algorithm=("batch_flip", None),
        n_iterations=(10**7, None),
    )
    assert _codes(validator, command) == ["out_of_range"]


def test_batch_reports_each_command(validator: SafetyValidator) -> None:
    results = validator.validate_batch(
        [
            _cmd("sim_laser", "set_power", power=(1.0, "mW")),
            _cmd("sim_laser", "set_power", power=(99.0, "mW")),
        ]
    )
    assert [r.accepted for r in results] == [True, False]
    assert not all_accepted(results)
    assert all_accepted(results[:1])
    assert not all_accepted([])


def test_blank_unit_means_no_unit(validator: SafetyValidator) -> None:
    command = _cmd("sim_slm", "configure", grid_side=(4, ""))
    assert command.parameters["grid_side"].unit is None
    assert validator.validate(command).accepted
