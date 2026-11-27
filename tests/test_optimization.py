"""Inner-loop optimizers on a noise-free optical Ising objective (N = 16)."""

import numpy as np
import pytest

from experimental_system.optimization import (
    BatchFlipOptimizer,
    InnerOptimizer,
    SimulatedAnnealingOptimizer,
    make_optimizer,
)
from experimental_system.scientific_core import ising, transmission
from experimental_system.scientific_core.types import FloatArray, SpinArray


def _problem(seed: int) -> tuple[FloatArray, float]:
    rng = np.random.default_rng(seed)
    tm = transmission.utc_matrix(64, 16, rng)
    coupling = ising.coupling_matrix(tm, [27])
    e_min, _ = ising.exact_ground_state(coupling)
    return coupling, e_min


def _gaps(algorithm: str, n_iterations: int) -> list[float]:
    gaps = []
    for seed in range(10):
        coupling, e_min = _problem(seed)

        def objective(spins: SpinArray, coupling: FloatArray = coupling) -> float:
            return float(-ising.energy(coupling, spins))

        result = make_optimizer(algorithm).run(
            objective, 16, n_iterations, np.random.default_rng(100 + seed)
        )
        gaps.append(ising.relative_energy_gap(-result.best_value, e_min))
    return gaps


@pytest.mark.parametrize("algorithm", ["batch_flip", "simulated_annealing"])
def test_enough_iterations_reach_ground_state(algorithm: str) -> None:
    gaps = _gaps(algorithm, 200)
    assert float(np.median(gaps)) < 1e-9
    assert all(g >= -1e-9 for g in gaps)  # never below the exact minimum


@pytest.mark.parametrize("algorithm", ["batch_flip", "simulated_annealing"])
def test_too_few_iterations_do_not(algorithm: str) -> None:
    assert float(np.median(_gaps(algorithm, 10))) > 0.1


@pytest.mark.parametrize("optimizer", [BatchFlipOptimizer(), SimulatedAnnealingOptimizer()])
def test_trajectory_is_best_so_far_and_deterministic(optimizer: InnerOptimizer) -> None:
    coupling, _ = _problem(0)

    def objective(spins: SpinArray) -> float:
        return float(-ising.energy(coupling, spins))

    a = optimizer.run(objective, 16, 50, np.random.default_rng(1))
    b = optimizer.run(objective, 16, 50, np.random.default_rng(1))
    assert np.array_equal(a.best_spins, b.best_spins)
    assert len(a.trajectory) == a.n_evaluations == 51
    assert np.all(np.diff(a.trajectory) >= 0)
    assert a.best_value == pytest.approx(objective(a.best_spins))


def test_batch_size_schedule() -> None:
    opt = BatchFlipOptimizer(initial_batch_fraction=0.12)
    sizes = [opt.batch_size(i, 1000, 256) for i in range(1000)]
    assert sizes[0] == 31  # ceil(0.12 * 256)
    assert sizes[-1] == 1
    assert all(a >= b for a, b in zip(sizes, sizes[1:], strict=False))
    assert sizes[700:] == [1] * 300


def test_unknown_algorithm() -> None:
    with pytest.raises(ValueError, match="unknown algorithm"):
        make_optimizer("gradient_descent")
