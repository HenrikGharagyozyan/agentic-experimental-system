"""Fast inner optimization loop over binary spin configurations.

The objective is a *measurement* (e.g. camera counts at the target modes) to be
maximised; the optimizer never sees T or J. One iteration = one objective evaluation, so
on hardware one iteration = one SLM update + one camera frame. The algorithm is a
parameter chosen by the agents (slow outer loop) between runs.
"""

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from experimental_system.scientific_core.types import FloatArray, SpinArray

Objective = Callable[[SpinArray], float]


@dataclass(frozen=True)
class OptimizationResult:
    best_spins: SpinArray
    best_value: float
    trajectory: FloatArray  # best-so-far objective after each evaluation (incl. the start)
    n_evaluations: int
    n_accepted: int


class InnerOptimizer(Protocol):
    @property
    def name(self) -> str: ...

    def run(
        self, objective: Objective, n_spins: int, n_iterations: int, rng: np.random.Generator
    ) -> OptimizationResult: ...


def _random_spins(n: int, rng: np.random.Generator) -> SpinArray:
    return np.asarray(rng.choice(np.array([-1, 1], dtype=np.int8), size=n), dtype=np.int8)


@dataclass(frozen=True)
class BatchFlipOptimizer:
    """Delloye et al. (2023): flip a random batch, keep it if the target intensity grew.

    The batch shrinks linearly from ``initial_batch_fraction * N`` spins to a single spin
    over the first ``1 - single_flip_fraction`` of the iterations; the rest are single
    flips (in the experiment: the last ~600 iterations).
    """

    initial_batch_fraction: float = 0.12
    single_flip_fraction: float = 0.3
    name: str = "batch_flip"

    def batch_size(self, iteration: int, n_iterations: int, n_spins: int) -> int:
        start = max(1, math.ceil(self.initial_batch_fraction * n_spins))
        ramp = max(1, int((1.0 - self.single_flip_fraction) * n_iterations))
        if iteration >= ramp:
            return 1
        return max(1, round(start + (1 - start) * iteration / ramp))

    def run(
        self, objective: Objective, n_spins: int, n_iterations: int, rng: np.random.Generator
    ) -> OptimizationResult:
        spins = _random_spins(n_spins, rng)
        current = objective(spins)
        trajectory = [current]
        accepted = 0
        for it in range(n_iterations):
            k = self.batch_size(it, n_iterations, n_spins)
            idx = rng.choice(n_spins, size=k, replace=False)
            candidate = spins.copy()
            candidate[idx] *= -1
            value = objective(candidate)
            if value > current:
                spins, current = candidate, value
                accepted += 1
            trajectory.append(current)
        return OptimizationResult(
            best_spins=spins,
            best_value=current,
            trajectory=np.asarray(trajectory, dtype=np.float64),
            n_evaluations=n_iterations + 1,
            n_accepted=accepted,
        )


@dataclass(frozen=True)
class SimulatedAnnealingOptimizer:
    """Metropolis single-spin flips with a geometric temperature schedule.

    Temperatures are relative to the objective scale: T_abs = T_rel * |objective(start)|,
    so the same settings work for any exposure / laser power.
    """

    temperature_start: float = 0.5
    temperature_end: float = 0.005
    name: str = "simulated_annealing"

    def run(
        self, objective: Objective, n_spins: int, n_iterations: int, rng: np.random.Generator
    ) -> OptimizationResult:
        spins = _random_spins(n_spins, rng)
        current = objective(spins)
        scale = max(abs(current), 1e-12)
        best_spins, best = spins.copy(), current
        trajectory = [best]
        accepted = 0
        ratio = self.temperature_end / self.temperature_start
        for it in range(n_iterations):
            frac = it / max(1, n_iterations - 1)
            temperature = scale * self.temperature_start * ratio**frac
            i = int(rng.integers(n_spins))
            candidate = spins.copy()
            candidate[i] *= -1
            value = objective(candidate)
            delta = value - current
            if delta > 0 or rng.random() < math.exp(delta / temperature):
                spins, current = candidate, value
                accepted += 1
                if current > best:
                    best_spins, best = spins.copy(), current
            trajectory.append(best)
        return OptimizationResult(
            best_spins=best_spins,
            best_value=best,
            trajectory=np.asarray(trajectory, dtype=np.float64),
            n_evaluations=n_iterations + 1,
            n_accepted=accepted,
        )


ALGORITHMS = ("batch_flip", "simulated_annealing")


def make_optimizer(
    algorithm: str,
    *,
    initial_batch_fraction: float = 0.12,
    temperature_start: float = 0.5,
    temperature_end: float = 0.005,
) -> InnerOptimizer:
    """Build an optimizer by name (names match the registry choices)."""
    if algorithm == "batch_flip":
        return BatchFlipOptimizer(initial_batch_fraction=initial_batch_fraction)
    if algorithm == "simulated_annealing":
        return SimulatedAnnealingOptimizer(
            temperature_start=temperature_start, temperature_end=temperature_end
        )
    raise ValueError(f"unknown algorithm {algorithm!r}; known: {ALGORITHMS}")
