"""Simulation backend: simulated optical setup + deterministic high-level procedures.

The *world* (which scattering medium is installed, noise, camera size, seeds) is fixed by
the scenario / CLI, never by the agents - just like the physical medium in a lab. Agents
control only what the Device Registry exposes.

SIMULATION HYPOTHESIS (not confirmed physics): the generator amplitude sets the interaction
length ell of the thin scattering medium,
    ell = ell_min + (ell_max - ell_min) * min(amplitude / amplitude_for_ell_max, 1)
when the generator output is on, and ell = ell_min when it is off. The thick (UTC) medium
ignores the generator.

Procedures run the fast inner loop here (thousands of SLM masks + camera frames) and
return only scalars and data_refs. Metrics are computed later by
``scientific_core.evaluation``.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np
from pydantic import Field

from experimental_system.devices.registry import DeviceRegistry, operation_defaults, parameter_spec
from experimental_system.devices.validator import SafetyValidator
from experimental_system.optimization import make_optimizer
from experimental_system.schemas.common import Contract, ScalarValue, utc_now
from experimental_system.schemas.devices import DeviceCommand
from experimental_system.schemas.execution import (
    DeviceStatus,
    ExecutionError,
    ExecutionResult,
    ExecutionStatus,
    Measurement,
)
from experimental_system.scientific_core import geometry, optics, transmission
from experimental_system.scientific_core import phase_retrieval as pr
from experimental_system.scientific_core.types import (
    ComplexArray,
    CountsArray,
    FloatArray,
    SpinArray,
)
from experimental_system.storage.run_store import ArrayStore

BACKEND_NAME = "simulation"
_SATURATED = optics.CAMERA_MAX_COUNTS
_MIN_SIGNAL_COUNTS = 5  # below this the procedure reports "no optical signal"


class SimulationWorld(Contract):
    """Hidden ground truth of the simulated lab (chosen by the scenario, not by agents)."""

    medium: Literal["utc", "thin"] = "utc"
    medium_seed: int = Field(default=0, ge=0)
    noise_seed: int = Field(default=1, ge=0)
    camera_grid_side: int = Field(default=8, ge=1, le=32)
    initial_slm_grid_side: int = Field(default=4, ge=2, le=16)
    camera_gain: float = Field(default=2.0, gt=0)  # counts / (mW * ms * unit intensity)
    read_noise: float = Field(default=0.5, ge=0)
    shot_noise: float = Field(default=0.5, ge=0)
    phase_levels: int = Field(default=256, ge=2)
    ell_min: float = Field(default=0.6, gt=0)
    ell_max: float = Field(default=3.0, gt=0)
    amplitude_for_ell_max: float = Field(default=10.0, gt=0)
    offline_devices: list[str] = Field(default_factory=list)


class ProcedureError(RuntimeError):
    """Expected, reportable failure of one command (becomes an ExecutionError)."""


@dataclass
class _Calibration:
    tm: ComplexArray
    grid_side: int
    ell: float | None


@dataclass
class _Output:
    measurements: list[Measurement]


class SimulationBackend:
    """Implements ``ExecutionBackend`` for the simulated optical setup."""

    def __init__(self, registry: DeviceRegistry, world: SimulationWorld, store: ArrayStore) -> None:
        self._registry = registry
        self._validator = SafetyValidator(registry)
        self._world = world
        self._store = store
        self._camera = optics.CameraModel(world.camera_gain, world.read_noise, world.shot_noise)
        self._noise_rng = np.random.default_rng(world.noise_seed)
        self._random_parts: dict[int, ComplexArray] = {}
        # device state
        self.laser_on = False
        self.laser_power = 0.0
        self.grid_side = world.initial_slm_grid_side
        self.generator_amplitude = 0.0
        self.generator_frequency = 1000.0
        self.generator_on = False
        self.exposure = 1.0
        self._mask: FloatArray | None = None
        self._calibration: _Calibration | None = None
        self.frames = 0
        exposure_spec = parameter_spec(registry, "sim_camera", "set_exposure", "exposure")
        self._exposure_min = (exposure_spec.minimum if exposure_spec else None) or 0.01
        self._exposure_max = (exposure_spec.maximum if exposure_spec else None) or 100.0

    # --- ExecutionBackend --------------------------------------------------------------------

    @property
    def name(self) -> str:
        return BACKEND_NAME

    def device_status(self, device_ids: Sequence[str] | None = None) -> list[DeviceStatus]:
        ids = (
            list(device_ids)
            if device_ids is not None
            else [d.device_id for d in self._registry.list_devices()]
        )
        statuses = []
        for device_id in ids:
            if self._registry.get_device(device_id) is None:
                statuses.append(
                    DeviceStatus(device_id=device_id, state="offline", message="unknown device")
                )
            elif device_id in self._world.offline_devices:
                statuses.append(
                    DeviceStatus(device_id=device_id, state="offline", message="not responding")
                )
            else:
                statuses.append(
                    DeviceStatus(device_id=device_id, state="ok", message=self._describe(device_id))
                )
        return statuses

    def execute(self, commands: Sequence[DeviceCommand]) -> ExecutionResult:
        started = utc_now()
        measurements: list[Measurement] = []
        errors: list[ExecutionError] = []
        done = 0
        for index, command in enumerate(commands):
            # Defense in depth: never trust the caller, re-validate every command.
            check = self._validator.validate(command)
            try:
                if not check.accepted:
                    reasons = "; ".join(v.message for v in check.violations)
                    raise ProcedureError(f"rejected by safety validator: {reasons}")
                if command.device_id in self._world.offline_devices:
                    raise ProcedureError(f"device {command.device_id!r} is offline")
                produced = self._dispatch(command).measurements
                measurements.extend(m.model_copy(update={"command_index": index}) for m in produced)
                done += 1
            except ProcedureError as exc:
                errors.append(
                    ExecutionError(
                        message=str(exc), step_id=command.step_id, device_id=command.device_id
                    )
                )
                break  # later commands may depend on this one
        if not errors:
            status = ExecutionStatus.SUCCESS
        elif done:
            status = ExecutionStatus.PARTIAL
        else:
            status = ExecutionStatus.FAILED
        return ExecutionResult(
            backend=self.name,
            status=status,
            measurements=measurements,
            device_statuses=self.device_status(),
            errors=errors,
            started_at=started,
            finished_at=utc_now(),
        )

    # --- dispatch ----------------------------------------------------------------------------

    def _dispatch(self, command: DeviceCommand) -> _Output:
        params = dict(operation_defaults(self._registry, command.device_id, command.operation))
        params.update({k: v.value for k, v in command.parameters.items()})
        handlers: dict[tuple[str, str], Callable[[str, dict[str, ScalarValue]], _Output]] = {
            ("sim_laser", "set_emission"): self._laser_emission,
            ("sim_laser", "set_power"): self._laser_power,
            ("sim_slm", "configure"): self._slm_configure,
            ("sim_generator", "configure"): self._generator_configure,
            ("sim_generator", "set_output"): self._generator_output,
            ("sim_camera", "set_exposure"): self._camera_exposure,
            ("sim_camera", "capture"): self._camera_capture,
            ("procedures", "calibrate_transmission_matrix"): self._calibrate,
            ("procedures", "run_ising_optimization"): self._run_ising,
            ("procedures", "focus"): self._focus,
        }
        handler = handlers.get((command.device_id, command.operation))
        if handler is None:
            raise ProcedureError(
                f"{command.device_id}.{command.operation} is not implemented by the simulation"
            )
        return handler(command.step_id, params)

    # --- simple devices ----------------------------------------------------------------------

    def _laser_emission(self, step: str, p: dict[str, ScalarValue]) -> _Output:
        self.laser_on = bool(p["enabled"])
        return _Output([])

    def _laser_power(self, step: str, p: dict[str, ScalarValue]) -> _Output:
        self.laser_power = float(p["power"])
        return _Output([])

    def _slm_configure(self, step: str, p: dict[str, ScalarValue]) -> _Output:
        side = int(p["grid_side"])
        if side != self.grid_side:
            self.grid_side = side
            self._mask = None
            self._calibration = None  # a different SLM grid invalidates the calibration
        return _Output([])

    def _generator_configure(self, step: str, p: dict[str, ScalarValue]) -> _Output:
        self.generator_amplitude = float(p["amplitude"])
        self.generator_frequency = float(p["frequency"])
        return _Output([])

    def _generator_output(self, step: str, p: dict[str, ScalarValue]) -> _Output:
        self.generator_on = bool(p["enabled"])
        return _Output([])

    def _camera_exposure(self, step: str, p: dict[str, ScalarValue]) -> _Output:
        self.exposure = float(p["exposure"])
        return _Output([])

    def _camera_capture(self, step: str, p: dict[str, ScalarValue]) -> _Output:
        n = self.grid_side**2
        mask = self._mask if self._mask is not None else self._rng_for(0).uniform(0, 2 * np.pi, n)
        frame = self._measure(mask[None, :], self.exposure)[0]
        ref = self._store.save_array(f"{step}_frame", frame)
        return _Output(
            [
                self._m(step, "sim_camera", "frame", float(frame.size), data_ref=ref),
                self._m(step, "sim_camera", "mean_counts", float(frame.mean()), unit="counts"),
                self._m(
                    step, "sim_camera", "saturation_fraction", optics.saturation_fraction(frame)
                ),
                self._m(step, "sim_camera", "n_frames", 1.0),
            ]
        )

    # --- physics of the simulated world ------------------------------------------------------

    @property
    def interaction_length(self) -> float | None:
        """Current ell of the thin medium (None for the UTC medium)."""
        w = self._world
        if w.medium != "thin":
            return None
        if not self.generator_on:
            return w.ell_min
        frac = min(max(self.generator_amplitude, 0.0) / w.amplitude_for_ell_max, 1.0)
        return w.ell_min + (w.ell_max - w.ell_min) * frac

    def true_tm(self) -> ComplexArray:
        """Ground-truth T for the current SLM grid and medium setting (simulation only)."""
        n = self.grid_side**2
        m = self._world.camera_grid_side**2
        if n not in self._random_parts:
            rng = np.random.default_rng([self._world.medium_seed, n])
            self._random_parts[n] = transmission.circular_gaussian((m, n), rng)
        g = self._random_parts[n]
        ell = self.interaction_length
        if ell is None:
            return np.asarray(g / np.sqrt(n), dtype=np.complex128)
        return transmission.thin_scatterer_matrix(
            g, self.grid_side, self._world.camera_grid_side, ell
        )

    def _measure(self, phases: FloatArray, exposure: float) -> CountsArray:
        """Display masks (K, N) on the SLM, capture K frames (K, M)."""
        shown = optics.quantize_phases(phases, self._world.phase_levels)
        light = optics.intensity(optics.propagate(self.true_tm(), optics.phase_field(shown)))
        power = self.laser_power if self.laser_on else 0.0
        self.frames += shown.shape[0]
        self._mask = shown[-1]
        return self._camera.capture(light, power, exposure, self._noise_rng)

    def _rng_for(self, seed: int) -> np.random.Generator:
        return np.random.default_rng([seed, self.frames])

    def _require_signal(self, frames: CountsArray) -> None:
        if int(frames.max()) < _MIN_SIGNAL_COUNTS:
            raise ProcedureError(
                "no optical signal on the camera (laser emission off or power/exposure too low)"
            )

    def _auto_exposure(self, probe_phases: FloatArray) -> float:
        """Pre-scan: scale exposure so the brightest pixel sits at 60-90% of full scale."""
        exposure = self.exposure
        for _ in range(12):
            frames = self._measure(probe_phases, exposure)
            peak = int(frames.max())
            if peak >= 0.9 * _SATURATED and exposure > self._exposure_min:
                exposure = max(self._exposure_min, exposure / 2)
            elif (
                peak < 0.6 * _SATURATED
                and exposure < self._exposure_max
                and peak >= _MIN_SIGNAL_COUNTS
            ):
                exposure = min(
                    self._exposure_max, exposure * min(2.0, 0.75 * _SATURATED / max(peak, 1))
                )
            else:
                break
        return exposure

    # --- procedures --------------------------------------------------------------------------

    def _calibrate(self, step: str, p: dict[str, ScalarValue]) -> _Output:
        n = self.grid_side**2
        n_probes = max(n, round(float(p["gamma"]) * n))
        rng = np.random.default_rng(int(p["seed"]))
        probe_phases = optics.quantize_phases(
            pr.random_phase_probes(n_probes, n, rng), self._world.phase_levels
        )
        exposure = (
            self._auto_exposure(probe_phases[:16]) if bool(p["auto_exposure"]) else self.exposure
        )
        frames = self._measure(probe_phases, exposure)
        self._require_signal(frames)
        amplitudes = np.sqrt(frames.astype(np.float64) / exposure)
        algorithm = str(p["algorithm"])
        if algorithm not in pr.GGS_SCHEDULES:
            raise ProcedureError(f"unknown calibration algorithm {algorithm!r}")
        result = pr.generalized_gs(
            optics.phase_field(probe_phases),
            amplitudes,
            algorithm=algorithm,
            max_iterations=int(p["max_iterations"]),
            rng=rng,
        )
        self._calibration = _Calibration(
            tm=result.tm, grid_side=self.grid_side, ell=self.interaction_length
        )
        est_ref = self._store.save_array(f"{step}_tm_estimate", result.tm)
        true_ref = self._store.save_array(f"{step}_tm_reference", self.true_tm())
        d = "procedures"
        return _Output(
            [
                self._m(step, d, "tm_estimate", float(result.tm.size), data_ref=est_ref),
                self._m(step, d, "tm_reference", float(result.tm.size), data_ref=true_ref),
                self._m(step, d, "calibration_iterations", float(sum(result.iterations))),
                self._m(step, d, "calibration_converged_fraction", result.converged_fraction),
                self._m(step, d, "calibration_probes", float(n_probes)),
                self._m(step, d, "n_pixels", float(n)),
                self._m(step, d, "exposure_used", exposure, unit="ms"),
                self._m(step, d, "saturation_fraction", optics.saturation_fraction(frames)),
                self._m(step, d, "n_frames", float(n_probes)),
            ]
        )

    def _targets(self, p: dict[str, ScalarValue]) -> list[int]:
        return geometry.target_modes(
            self._world.camera_grid_side,
            self.grid_side,
            int(p["n_targets"]),
            float(p["target_separation"]),
        )

    def _run_ising(self, step: str, p: dict[str, ScalarValue]) -> _Output:
        n = self.grid_side**2
        targets = self._targets(p)
        auto = bool(p["auto_exposure"])
        state = {"exposure": self.exposure, "saturated": 0, "evaluations": 0}
        bias = np.zeros(n)
        if str(p["bias"]) == "calibrated_tm":
            cal = self._valid_calibration()
            bias = np.asarray(-np.angle(cal.tm[targets, :].sum(axis=0)), dtype=np.float64)

        def objective(spins: SpinArray) -> float:
            """Measured target counts per ms for one spin configuration (one frame)."""
            phases = (optics.spins_to_phases(spins) + bias)[None, :]
            while True:
                frame = self._measure(phases, state["exposure"])[0]
                hit = bool((frame[targets] >= _SATURATED).any())
                if hit and auto and state["exposure"] > self._exposure_min:
                    state["exposure"] = max(self._exposure_min, state["exposure"] / 2)
                    continue
                break
            state["evaluations"] += 1
            state["saturated"] += int(hit)
            return float(frame[targets].sum()) / state["exposure"]

        start_frames = self.frames
        optimizer = make_optimizer(
            str(p["algorithm"]),
            initial_batch_fraction=float(p["initial_batch_fraction"]),
            temperature_start=float(p["temperature_start"]),
            temperature_end=float(p["temperature_end"]),
        )
        replicas, trajectories = [], []
        for r in range(int(p["n_replicas"])):
            result = optimizer.run(
                objective, n, int(p["n_iterations"]), np.random.default_rng([int(p["seed"]), r])
            )
            replicas.append(result.best_spins)
            trajectories.append(result.trajectory)
        if max(float(t.max()) for t in trajectories) * state["exposure"] < _MIN_SIGNAL_COUNTS:
            raise ProcedureError(
                "no optical signal on the camera (laser emission off or power/exposure too low)"
            )
        d = "procedures"
        store = self._store
        out = [
            self._m(
                step,
                d,
                "ising_replicas",
                float(n * len(replicas)),
                data_ref=store.save_array(f"{step}_replicas", np.stack(replicas)),
            ),
            self._m(
                step,
                d,
                "ising_trajectories",
                float(sum(len(t) for t in trajectories)),
                data_ref=store.save_array(f"{step}_trajectories", np.stack(trajectories)),
            ),
            self._m(
                step,
                d,
                "ising_targets",
                float(len(targets)),
                data_ref=store.save_array(f"{step}_targets", np.asarray(targets, dtype=np.int64)),
            ),
            self._m(
                step,
                d,
                "tm_reference",
                float(n),
                # Effective T seen by the spins (phase bias folded in): J follows from it.
                data_ref=store.save_array(
                    f"{step}_tm_reference", self.true_tm() * np.exp(1j * bias)[None, :]
                ),
            ),
            self._m(
                step,
                d,
                "best_target_signal",
                max(float(t[-1]) for t in trajectories),
                unit="counts/ms",
            ),
            self._m(step, d, "n_pixels", float(n)),
            self._m(step, d, "exposure_used", float(state["exposure"]), unit="ms"),
            self._m(
                step, d, "saturation_fraction", state["saturated"] / max(1, state["evaluations"])
            ),
            self._m(step, d, "n_frames", float(self.frames - start_frames)),
        ]
        ell = self.interaction_length
        if ell is not None:
            out.append(self._m(step, d, "sim_interaction_length", ell, unit="px"))
        if str(p["bias"]) == "calibrated_tm":
            stale = self._valid_calibration().ell != ell
            out.append(self._m(step, d, "calibration_stale", float(stale)))
        return _Output(out)

    def _focus(self, step: str, p: dict[str, ScalarValue]) -> _Output:
        cal = self._valid_calibration()
        n = self.grid_side**2
        targets = self._targets(p)
        if str(p["method"]) == "gs_tm":
            amplitude = np.zeros(cal.tm.shape[0])
            amplitude[targets] = 1.0
            result = pr.gerchberg_saxton(
                pr.MatrixPropagator(cal.tm),
                np.ones(n),
                amplitude,
                n_iterations=100,
                rng=np.random.default_rng(int(p["seed"])),
            )
            mask = result.phases
        else:
            mask = pr.focusing_phases(cal.tm, targets)
        start_frames = self.frames
        focus_phases = np.repeat(mask[None, :], 5, axis=0)
        focus_exposure = self._auto_exposure(focus_phases[:1])
        focus_frames = self._measure(focus_phases, focus_exposure)
        self._require_signal(focus_frames)
        rng = np.random.default_rng(int(p["seed"]) + 1)
        ref_phases = rng.uniform(0, 2 * np.pi, size=(int(p["n_reference_masks"]), n))
        ref_exposure = self._auto_exposure(ref_phases[:16])
        ref_frames = self._measure(ref_phases, ref_exposure)
        focus_signal = float(focus_frames[:, targets].mean()) / focus_exposure
        ref_signal = float(ref_frames[:, targets].mean()) / ref_exposure
        d = "procedures"
        stale = cal.ell != self.interaction_length
        self._mask = mask
        return _Output(
            [
                self._m(
                    step,
                    d,
                    "focus_frame",
                    float(focus_frames[0].size),
                    data_ref=self._store.save_array(f"{step}_focus_frame", focus_frames[0]),
                ),
                self._m(step, d, "focus_intensity", focus_signal, unit="counts/ms"),
                self._m(step, d, "reference_intensity", ref_signal, unit="counts/ms"),
                self._m(step, d, "n_foci", float(len(targets))),
                self._m(step, d, "n_pixels", float(n)),
                self._m(step, d, "calibration_stale", float(stale)),
                self._m(
                    step,
                    d,
                    "saturation_fraction",
                    max(
                        optics.saturation_fraction(focus_frames),
                        optics.saturation_fraction(ref_frames),
                    ),
                ),
                self._m(step, d, "n_frames", float(self.frames - start_frames)),
            ]
        )

    # --- helpers -----------------------------------------------------------------------------

    def _valid_calibration(self) -> _Calibration:
        cal = self._calibration
        if cal is None or cal.grid_side != self.grid_side:
            raise ProcedureError(
                "this procedure requires calibrate_transmission_matrix for the current SLM grid"
            )
        return cal

    @staticmethod
    def _m(
        step: str,
        device: str,
        name: str,
        value: float,
        *,
        unit: str | None = None,
        data_ref: str | None = None,
    ) -> Measurement:
        return Measurement(
            name=name,
            value=float(value),
            unit=unit,
            step_id=step,
            device_id=device,
            data_ref=data_ref,
        )

    def _describe(self, device_id: str) -> str:
        if device_id == "sim_laser":
            return f"emission {'on' if self.laser_on else 'off'}, power {self.laser_power} mW"
        if device_id == "sim_slm":
            return f"grid_side {self.grid_side} (N = {self.grid_side**2})"
        if device_id == "sim_generator":
            return (
                f"output {'on' if self.generator_on else 'off'}, amplitude "
                f"{self.generator_amplitude} V, frequency {self.generator_frequency} Hz"
            )
        if device_id == "sim_camera":
            return f"exposure {self.exposure} ms, mono8"
        if device_id == "procedures":
            calibrated = (
                self._calibration is not None and self._calibration.grid_side == self.grid_side
            )
            return f"transmission matrix calibrated: {'yes' if calibrated else 'no'}"
        return ""
