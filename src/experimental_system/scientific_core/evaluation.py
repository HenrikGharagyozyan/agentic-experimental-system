"""ExecutionResult -> Metrics: deterministic numbers for the Analyst.

The backend returns raw measurements (scalars + data_refs to arrays). Here every derived
number is computed by scientific_core functions, and success criteria are evaluated in
code. An LLM never produces any of these values.
"""

import math
import operator
from collections import OrderedDict
from collections.abc import Callable, Sequence
from typing import Any

import numpy as np
import numpy.typing as npt

from experimental_system.schemas.analysis import CriterionResult, Metrics
from experimental_system.schemas.execution import ExecutionResult, Measurement
from experimental_system.schemas.task import SuccessCriterion
from experimental_system.scientific_core import ising, metrics
from experimental_system.scientific_core.catalog import METRICS

ArrayLoader = Callable[[str], npt.NDArray[Any]]

_OPS: dict[str, Callable[[float, float], bool]] = {
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
}


def evaluate_criteria(
    values: dict[str, float], criteria: Sequence[SuccessCriterion]
) -> list[CriterionResult]:
    """Check ``values[metric] <op> target``; a missing metric fails the criterion."""
    results = []
    for criterion in criteria:
        observed = values.get(criterion.metric)
        passed = observed is not None and _OPS[criterion.op](observed, criterion.target)
        results.append(CriterionResult(criterion=criterion, observed=observed, passed=passed))
    return results


def compute_metrics(
    execution: ExecutionResult, load: ArrayLoader, criteria: Sequence[SuccessCriterion]
) -> Metrics:
    values = compute_values(execution, load)
    return Metrics(values=values, criteria=evaluate_criteria(values, criteria))


def compute_values(execution: ExecutionResult, load: ArrayLoader) -> dict[str, float]:
    # One group per producing command (fallback: per step) - preserves execution order.
    steps: OrderedDict[str, dict[str, Measurement]] = OrderedDict()
    for m in execution.measurements:
        key = f"c{m.command_index}" if m.command_index is not None else f"s:{m.step_id}"
        steps.setdefault(key, {})[m.name] = m

    values: dict[str, float] = {}
    frames = [m.value for m in execution.measurements if m.name == "n_frames"]
    if frames:
        values["n_measurements"] = float(sum(frames))
    saturation = [m.value for m in execution.measurements if m.name == "saturation_fraction"]
    if saturation:
        values["saturation_fraction"] = float(max(saturation))

    ising_runs = [s for s in steps.values() if "ising_replicas" in s]
    for step in steps.values():
        if "tm_estimate" in step:
            values.update(_calibration_values(step, load))
        if "focus_intensity" in step:
            values.update(_focus_values(step))
    if ising_runs:
        first = _ising_values(ising_runs[0], load)
        last = _ising_values(ising_runs[-1], load) if len(ising_runs) > 1 else first
        values.update(last)
        if len(ising_runs) > 1 and "replica_overlap" in first and "replica_overlap" in last:
            values["replica_overlap_change"] = last["replica_overlap"] - first["replica_overlap"]

    unknown = set(values) - set(METRICS)
    if unknown:  # programming error: catalog and evaluation out of sync
        raise RuntimeError(f"metrics missing from the catalog: {sorted(unknown)}")
    return {k: v for k, v in values.items() if math.isfinite(v)}


def _ref(step: dict[str, Measurement], name: str) -> str:
    ref = step[name].data_ref
    if ref is None:
        raise ValueError(f"measurement {name!r} has no data_ref")
    return ref


def _calibration_values(step: dict[str, Measurement], load: ArrayLoader) -> dict[str, float]:
    out = {
        "calibration_iterations": step["calibration_iterations"].value,
        "calibration_converged_fraction": step["calibration_converged_fraction"].value,
    }
    if "tm_reference" in step:
        estimate = load(_ref(step, "tm_estimate"))
        truth = load(_ref(step, "tm_reference"))
        out["tm_correlation"] = float(metrics.row_correlations(estimate, truth).mean())
    return out


def _focus_values(step: dict[str, Measurement]) -> dict[str, float]:
    eta = metrics.enhancement(step["focus_intensity"].value, step["reference_intensity"].value)
    theory = metrics.theoretical_enhancement_phase_only(
        int(step["n_pixels"].value), int(step["n_foci"].value)
    )
    return {"enhancement": eta, "enhancement_theory": theory, "enhancement_ratio": eta / theory}


def _ising_values(step: dict[str, Measurement], load: ArrayLoader) -> dict[str, float]:
    replicas = load(_ref(step, "ising_replicas")).astype(np.int8)
    trajectories = load(_ref(step, "ising_trajectories"))
    targets = [int(t) for t in load(_ref(step, "ising_targets"))]
    tm = load(_ref(step, "tm_reference"))
    coupling = ising.coupling_matrix(tm, targets)
    energies = ising.energy(coupling, replicas)
    best = int(np.argmin(energies))
    out = {
        "energy": float(energies[best]),
        "magnetization": ising.magnetization(replicas[best]),
        "plateau_fraction": float(np.mean([metrics.has_plateau(-traj) for traj in trajectories])),
    }
    if "best_target_signal" in step:
        out["target_signal"] = step["best_target_signal"].value
    if replicas.shape[1] <= ising.MAX_EXACT_SPINS:
        e_min, ground = ising.exact_ground_state(coupling)
        out["energy_min_exact"] = e_min
        out["energy_gap"] = ising.relative_energy_gap(out["energy"], e_min)
        out["ground_state_overlap"] = abs(ising.overlap(replicas[best], ground))
    if replicas.shape[0] >= 2:
        roi = ising.region_of_interest(tm, targets)
        out["replica_overlap"] = float(ising.replica_overlaps(replicas, roi).mean())
    return out
