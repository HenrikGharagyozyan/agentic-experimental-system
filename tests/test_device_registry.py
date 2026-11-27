"""YAML Device Registry: loading, lookups, defaults and config errors."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from experimental_system.devices import DeviceRegistry, RegistryError, YamlDeviceRegistry
from experimental_system.schemas import RegistryDocument
from factories import make_device


def test_simulation_registry_loads(sim_registry: YamlDeviceRegistry) -> None:
    assert isinstance(sim_registry, DeviceRegistry)
    assert sim_registry.simulation_only
    assert "simulation only" in sim_registry.document.notice
    ids = {d.device_id for d in sim_registry.list_devices()}
    assert ids == {"sim_laser", "sim_slm", "sim_generator", "sim_camera", "procedures"}


def test_procedures_are_a_virtual_device(sim_registry: YamlDeviceRegistry) -> None:
    procedures = sim_registry.get_device("procedures")
    assert procedures is not None
    names = {o.name for o in procedures.operations}
    assert names == {"calibrate_transmission_matrix", "run_ising_optimization", "focus"}


def test_defaults(sim_registry: YamlDeviceRegistry) -> None:
    defaults = sim_registry.defaults("procedures", "calibrate_transmission_matrix")
    assert defaults["algorithm"] == "ggs_2_1"
    assert "gamma" not in defaults  # required -> no default
    assert sim_registry.defaults("nope", "x") == {}


def test_unknown_device_is_none(sim_registry: YamlDeviceRegistry) -> None:
    assert sim_registry.get_device("real_laser") is None


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(RegistryError):
        YamlDeviceRegistry.from_file(tmp_path / "missing.yaml")


def test_invalid_default_is_rejected_at_load() -> None:
    device = make_device().model_dump()
    device["operations"][0]["parameters"][0].update(required=False, default=900.0)
    doc = RegistryDocument.model_validate(
        {"name": "t", "simulation_only": True, "devices": [device]}
    )
    with pytest.raises(RegistryError, match="invalid default"):
        YamlDeviceRegistry(doc)


def test_duplicate_device_ids_rejected() -> None:
    device = make_device().model_dump()
    with pytest.raises(ValidationError, match="duplicate device_id"):
        RegistryDocument.model_validate(
            {"name": "t", "simulation_only": True, "devices": [device, device]}
        )


def test_duplicate_parameter_names_rejected() -> None:
    device = make_device().model_dump()
    params = device["operations"][0]["parameters"]
    params.append(params[0])
    with pytest.raises(ValidationError, match="duplicate"):
        RegistryDocument.model_validate({"name": "t", "simulation_only": True, "devices": [device]})


def test_required_parameter_with_default_rejected() -> None:
    device = make_device().model_dump()
    device["operations"][0]["parameters"][0]["default"] = 1.0
    with pytest.raises(ValidationError, match="required parameter has no default"):
        RegistryDocument.model_validate({"name": "t", "simulation_only": True, "devices": [device]})
