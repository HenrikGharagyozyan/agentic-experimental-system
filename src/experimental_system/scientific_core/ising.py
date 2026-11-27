"""Optical Ising model (Delloye et al. 2023; Pierangeli et al. 2019).

Spins sigma_i = ±1 are binary phases on the SLM. For target camera modes S:

    H(sigma) = - sum_{m in S} I_m = - sum_{i,j} J_ij sigma_i sigma_j,
    J_ij = Re sum_{m in S} t_mi * conj(t_mj).

(The sign convention follows the self-consistent form; see docs/DEVLOG.md.)
"""

from collections.abc import Sequence
from itertools import combinations

import numpy as np

from experimental_system.scientific_core.optics import intensity, propagate
from experimental_system.scientific_core.types import ComplexArray, FloatArray, SpinArray

MAX_EXACT_SPINS = 20


def coupling_matrix(tm: ComplexArray, targets: Sequence[int]) -> FloatArray:
    """J (N x N, symmetric, real) for the target modes."""
    rows = tm[list(targets), :]
    return np.real(rows.T @ np.conj(rows)).astype(np.float64)


def energy_optical(tm: ComplexArray, targets: Sequence[int], spins: SpinArray) -> FloatArray:
    """H = -(intensity summed over target modes) for spins (N,) or a batch (K, N)."""
    field = propagate(tm, spins.astype(np.complex128))
    light = intensity(field)
    return np.asarray(-light[..., list(targets)].sum(axis=-1), dtype=np.float64)


def energy(coupling: FloatArray, spins: SpinArray) -> FloatArray:
    """H = -sigma^T J sigma for spins (N,) or a batch (K, N)."""
    s = spins.astype(np.float64)
    return np.asarray(-np.einsum("...i,ij,...j->...", s, coupling, s), dtype=np.float64)


def exact_ground_state(coupling: FloatArray, chunk: int = 1 << 15) -> tuple[float, SpinArray]:
    """Brute-force minimum of H over all 2^N configurations (N <= 20).

    Uses the global-flip symmetry H(sigma) = H(-sigma): sigma_0 is fixed to +1, so only
    2^(N-1) configurations are evaluated, in vectorised chunks.
    """
    n = coupling.shape[0]
    if n > MAX_EXACT_SPINS:
        raise ValueError(f"exact enumeration is limited to N <= {MAX_EXACT_SPINS}, got {n}")
    total = 1 << (n - 1)
    bits = np.arange(n - 1, dtype=np.int64)
    best_energy = np.inf
    best = np.ones(n, dtype=np.int8)
    for start in range(0, total, chunk):
        codes = np.arange(start, min(start + chunk, total), dtype=np.int64)
        rest = 1 - 2 * ((codes[:, None] >> bits[None, :]) & 1)
        spins = np.concatenate([np.ones((len(codes), 1), dtype=np.int64), rest], axis=1)
        energies = energy(coupling, spins.astype(np.int8))
        k = int(np.argmin(energies))
        if energies[k] < best_energy:
            best_energy = float(energies[k])
            best = spins[k].astype(np.int8)
    return best_energy, best


def relative_energy_gap(value: float, ground: float) -> float:
    """(E - E_min) / |E_min|; 0 means the ground state was reached."""
    if ground == 0:
        raise ValueError("ground-state energy is zero; relative gap undefined")
    return (value - ground) / abs(ground)


def magnetization(spins: SpinArray) -> float:
    """|mean(sigma)| (absolute because of the global-flip symmetry)."""
    return float(abs(np.mean(spins.astype(np.float64))))


def overlap(a: SpinArray, b: SpinArray, mask: np.typing.NDArray[np.bool_] | None = None) -> float:
    """Parisi overlap q = (1/N) sum_i a_i b_i over the masked spins (signed)."""
    if mask is not None:
        a, b = a[mask], b[mask]
    if a.size == 0:
        raise ValueError("overlap over an empty set of spins")
    return float(np.mean(a.astype(np.float64) * b.astype(np.float64)))


def replica_overlaps(
    replicas: SpinArray, mask: np.typing.NDArray[np.bool_] | None = None
) -> FloatArray:
    """|q| for every pair of replicas (rows of ``replicas``)."""
    pairs = combinations(range(replicas.shape[0]), 2)
    return np.array([abs(overlap(replicas[a], replicas[b], mask)) for a, b in pairs])


def region_of_interest(
    tm: ComplexArray, targets: Sequence[int], fraction: float = 0.1
) -> np.typing.NDArray[np.bool_]:
    """Spins actually coupled to the targets: sum_m |t_mi|^2 >= fraction * max.

    Like Delloye's "zone of interest": spins with negligible coupling are free (they do
    not change the energy), so including them would add pure noise to the overlap.
    """
    weight = (np.abs(tm[list(targets), :]) ** 2).sum(axis=0)
    return np.asarray(weight >= fraction * weight.max())
