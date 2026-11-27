"""Catalog of metrics that scientific_core can compute.

This is the single source of truth for metric names: the Scientist may only use these in
success criteria, and the Analyst may only reference metrics that were actually computed.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class MetricInfo:
    description: str
    produced_by: str  # procedure / operation that provides the inputs
    better: str  # "lower" | "higher" | "-"


METRICS: dict[str, MetricInfo] = {
    "energy": MetricInfo(
        "Ising energy H = -sum_{m in S} I_m of the best replica of the last optimization run "
        "(model units, from the reference transmission matrix).",
        "run_ising_optimization",
        "lower",
    ),
    "energy_min_exact": MetricInfo(
        "Exact ground-state energy by brute force (only for N <= 20 spins).",
        "run_ising_optimization",
        "-",
    ),
    "energy_gap": MetricInfo(
        "Relative gap (energy - energy_min_exact) / |energy_min_exact|; 0 = ground state "
        "reached (only for N <= 20).",
        "run_ising_optimization",
        "lower",
    ),
    "ground_state_overlap": MetricInfo(
        "|q| between the best replica and the exact ground state, in [0, 1] (N <= 20).",
        "run_ising_optimization",
        "higher",
    ),
    "magnetization": MetricInfo(
        "|mean spin| of the best replica, in [0, 1].", "run_ising_optimization", "-"
    ),
    "replica_overlap": MetricInfo(
        "Mean |q| = |(1/N) sum_i s_i^a s_i^b| over replica pairs, restricted to spins coupled "
        "to the targets (needs n_replicas >= 2), last optimization run.",
        "run_ising_optimization",
        "-",
    ),
    "replica_overlap_change": MetricInfo(
        "replica_overlap of the last optimization run minus that of the first run in the "
        "same iteration (needs >= 2 runs).",
        "run_ising_optimization",
        "-",
    ),
    "plateau_fraction": MetricInfo(
        "Fraction of replicas whose energy trajectory reached a plateau (converged), in [0, 1].",
        "run_ising_optimization",
        "higher",
    ),
    "target_signal": MetricInfo(
        "Best measured target intensity of the last optimization run (camera counts per ms).",
        "run_ising_optimization",
        "higher",
    ),
    "tm_correlation": MetricInfo(
        "Mean row correlation |<t_est, t_true>| / (|t_est||t_true|) of the retrieved "
        "transmission matrix, in [0, 1] (simulation only: needs the true T).",
        "calibrate_transmission_matrix",
        "higher",
    ),
    "calibration_iterations": MetricInfo(
        "GGS iterations used (all stages).", "calibrate_transmission_matrix", "lower"
    ),
    "calibration_converged_fraction": MetricInfo(
        "Fraction of TM rows that met the GGS convergence tolerance.",
        "calibrate_transmission_matrix",
        "higher",
    ),
    "enhancement": MetricInfo(
        "Focusing enhancement eta = I_focus / <I>_random at the target mode(s).", "focus", "higher"
    ),
    "enhancement_theory": MetricInfo(
        "Theoretical eta for continuous phase-only modulation: pi/4 (N-1)/N_f + 1.",
        "focus",
        "-",
    ),
    "enhancement_ratio": MetricInfo(
        "enhancement / enhancement_theory, typically in [0, 1].", "focus", "higher"
    ),
    "n_measurements": MetricInfo(
        "Camera frames used in this iteration (experimental cost).", "any", "lower"
    ),
    "saturation_fraction": MetricInfo(
        "Worst fraction of saturated camera pixels/evaluations (8-bit ceiling).", "any", "lower"
    ),
}


def describe_metrics() -> str:
    """Bullet list for agent prompts."""
    return "\n".join(
        f"- {name} (better: {info.better}; from {info.produced_by}): {info.description}"
        for name, info in METRICS.items()
    )
