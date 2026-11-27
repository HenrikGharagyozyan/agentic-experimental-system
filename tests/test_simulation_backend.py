"""Simulation backend: devices, procedures, errors, defense in depth (small N)."""

from pathlib import Path

import numpy as np
import pytest

from experimental_system.backends import ExecutionBackend
from experimental_system.backends.simulation import SimulationBackend, SimulationWorld
from experimental_system.devices import YamlDeviceRegistry
from experimental_system.schemas import ExecutionStatus
from experimental_system.scientific_core.evaluation import compute_values
from experimental_system.storage import RunStore
from simhelpers import LASER_ON, cmd


def _backend(
    registry: YamlDeviceRegistry, tmp_path: Path, **world: object
) -> tuple[SimulationBackend, RunStore]:
    store = RunStore(tmp_path, "exp")
    return SimulationBackend(registry, SimulationWorld.model_validate(world), store), store


def test_satisfies_protocol(sim_registry: YamlDeviceRegistry, tmp_path: Path) -> None:
    backend, _ = _backend(sim_registry, tmp_path)
    assert isinstance(backend, ExecutionBackend)
    assert backend.name == "simulation"


def test_device_state_and_status(sim_registry: YamlDeviceRegistry, tmp_path: Path) -> None:
    backend, _ = _backend(sim_registry, tmp_path, offline_devices=["sim_generator"])
    result = backend.execute([*LASER_ON, cmd("sim_slm", "configure", grid_side=5)])
    assert result.status is ExecutionStatus.SUCCESS
    assert backend.laser_on and backend.laser_power == 10.0 and backend.grid_side == 5
    statuses = {s.device_id: s for s in backend.device_status()}
    assert statuses["sim_generator"].state == "offline"
    assert statuses["sim_laser"].message is not None and "on" in statuses["sim_laser"].message
    assert backend.device_status(["nope"])[0].state == "offline"


def test_backend_revalidates_commands(sim_registry: YamlDeviceRegistry, tmp_path: Path) -> None:
    backend, _ = _backend(sim_registry, tmp_path)
    result = backend.execute([cmd("sim_laser", "set_power", power=(500.0, "mW"))])
    assert result.status is ExecutionStatus.FAILED
    assert "safety validator" in result.errors[0].message
    assert backend.laser_power == 0.0  # never applied, never clamped


def test_offline_device_fails(sim_registry: YamlDeviceRegistry, tmp_path: Path) -> None:
    backend, _ = _backend(sim_registry, tmp_path, offline_devices=["sim_laser"])
    result = backend.execute(LASER_ON)
    assert result.status is ExecutionStatus.FAILED
    assert "offline" in result.errors[0].message


def test_laser_off_gives_no_signal_error(sim_registry: YamlDeviceRegistry, tmp_path: Path) -> None:
    backend, _ = _backend(sim_registry, tmp_path)
    result = backend.execute(
        [
            cmd("sim_camera", "set_exposure", exposure=(1.0, "ms")),
            cmd("procedures", "run_ising_optimization", algorithm="batch_flip", n_iterations=10),
            cmd("sim_camera", "capture"),
        ]
    )
    assert result.status is ExecutionStatus.PARTIAL  # first command ran, then stop
    assert len(result.errors) == 1 and "no optical signal" in result.errors[0].message


def test_focus_requires_calibration(sim_registry: YamlDeviceRegistry, tmp_path: Path) -> None:
    backend, _ = _backend(sim_registry, tmp_path)
    result = backend.execute([*LASER_ON, cmd("procedures", "focus")])
    assert result.status is ExecutionStatus.PARTIAL
    assert "requires calibrate_transmission_matrix" in result.errors[0].message


def test_capture(sim_registry: YamlDeviceRegistry, tmp_path: Path) -> None:
    backend, store = _backend(sim_registry, tmp_path)
    result = backend.execute([*LASER_ON, cmd("sim_camera", "capture")])
    by_name = {m.name: m for m in result.measurements}
    assert by_name["frame"].data_ref is not None
    frame = store.load_array(by_name["frame"].data_ref)
    assert frame.dtype == np.uint8 and frame.shape == (64,)
    assert by_name["mean_counts"].value > 0
    assert all(m.command_index == 2 for m in result.measurements)


def test_ising_weak_vs_strong(sim_registry: YamlDeviceRegistry, tmp_path: Path) -> None:
    values = []
    for n_iterations, replicas in ((10, 1), (200, 4)):
        backend, store = _backend(sim_registry, tmp_path / str(n_iterations))
        result = backend.execute(
            [
                *LASER_ON,
                cmd(
                    "procedures",
                    "run_ising_optimization",
                    algorithm="batch_flip",
                    n_iterations=n_iterations,
                    n_replicas=replicas,
                ),
            ]
        )
        assert result.status is ExecutionStatus.SUCCESS
        values.append(compute_values(result, store.load_array))
    weak, strong = values
    assert weak["energy_gap"] > 0.1
    assert strong["energy_gap"] < 1e-9
    assert strong["n_measurements"] == 4 * 201
    assert "replica_overlap" in strong and "replica_overlap" not in weak


def test_calibration_and_focusing(sim_registry: YamlDeviceRegistry, tmp_path: Path) -> None:
    backend, store = _backend(sim_registry, tmp_path)
    result = backend.execute(
        [
            *LASER_ON,
            cmd("sim_slm", "configure", grid_side=6),
            cmd("procedures", "calibrate_transmission_matrix", gamma=4.0),
            cmd("procedures", "focus"),
        ]
    )
    assert result.status is ExecutionStatus.SUCCESS, result.errors
    values = compute_values(result, store.load_array)
    assert values["tm_correlation"] > 0.85
    assert values["enhancement_ratio"] > 0.7
    assert values["saturation_fraction"] < 0.01


def test_changing_grid_invalidates_calibration(
    sim_registry: YamlDeviceRegistry, tmp_path: Path
) -> None:
    backend, _ = _backend(sim_registry, tmp_path)
    result = backend.execute(
        [
            *LASER_ON,
            cmd("procedures", "calibrate_transmission_matrix", gamma=2.0, max_iterations=50),
            cmd("sim_slm", "configure", grid_side=5),
            cmd("procedures", "focus"),
        ]
    )
    assert result.status is ExecutionStatus.PARTIAL


def test_generator_controls_thin_medium(sim_registry: YamlDeviceRegistry, tmp_path: Path) -> None:
    backend, _ = _backend(sim_registry, tmp_path, medium="thin")
    assert backend.interaction_length == pytest.approx(0.6)
    backend.execute(
        [
            cmd("sim_generator", "configure", amplitude=(5.0, "V")),
            cmd("sim_generator", "set_output", enabled=True),
        ]
    )
    assert backend.interaction_length == pytest.approx(0.6 + 2.4 * 0.5)
    utc, _ = _backend(sim_registry, tmp_path / "utc")
    assert utc.interaction_length is None


def test_two_foci_overlap_grows_with_coupling(
    sim_registry: YamlDeviceRegistry, tmp_path: Path
) -> None:
    """Scenario-3 physics: with the TM bias, stronger coupling -> correlated regions."""
    commands = [*LASER_ON, cmd("sim_slm", "configure", grid_side=6)]
    for k, amplitude in enumerate((1.7, 10.0)):
        step = f"v{k}"
        commands += [
            cmd("sim_generator", "configure", step=step, amplitude=(amplitude, "V")),
            cmd("sim_generator", "set_output", step=step, enabled=True),
            cmd("procedures", "calibrate_transmission_matrix", step=step, gamma=4.0),
            cmd(
                "procedures",
                "run_ising_optimization",
                step=step,
                algorithm="batch_flip",
                n_iterations=360,
                n_targets=2,
                target_separation=(3.0, "px"),
                n_replicas=10,
                bias="calibrated_tm",
            ),
        ]
    backend, store = _backend(sim_registry, tmp_path, medium="thin")
    result = backend.execute(commands)
    assert result.status is ExecutionStatus.SUCCESS, result.errors
    values = compute_values(result, store.load_array)
    assert values["replica_overlap"] > 0.8
    assert values["replica_overlap_change"] > 0.2
