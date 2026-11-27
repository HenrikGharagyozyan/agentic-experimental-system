"""Scalar metrics of focusing, calibration quality and convergence."""

import math

import numpy as np

from experimental_system.scientific_core.types import ComplexArray, FloatArray


def row_correlations(estimate: ComplexArray, truth: ComplexArray) -> FloatArray:
    """|<x_hat, x>| / (|x_hat| |x|) per row: invariant to the unknown phase of each row.

    Phase retrieval recovers every row of T only up to a global phase factor, so a plain
    element-wise error would be meaningless.
    """
    if estimate.shape != truth.shape:
        raise ValueError(f"shape mismatch {estimate.shape} vs {truth.shape}")
    inner = np.abs(np.sum(np.conj(estimate) * truth, axis=1))
    norms = np.linalg.norm(estimate, axis=1) * np.linalg.norm(truth, axis=1)
    return np.asarray(inner / np.where(norms > 0, norms, np.inf), dtype=np.float64)


def enhancement(focus_intensity: float, reference_intensity: float) -> float:
    """eta = I_focus / <I>_random (Vellekoop & Mosk 2007)."""
    if reference_intensity <= 0:
        raise ValueError("reference intensity must be > 0")
    return focus_intensity / reference_intensity


def theoretical_enhancement_phase_only(n_pixels: int, n_foci: int = 1) -> float:
    """Continuous phase-only modulation: eta = pi/4 * (N - 1) / N_f + 1.

    Huang et al. (2021): eta = pi(N-1)/4 + 1 for one focus; for N_f simultaneous foci
    "an additional N_f in the denominator". NOT valid for binary (0/pi) modulation.
    """
    if n_pixels < 1 or n_foci < 1:
        raise ValueError("n_pixels and n_foci must be >= 1")
    return math.pi / 4.0 * (n_pixels - 1) / n_foci + 1.0


def has_plateau(
    trajectory: FloatArray, window_fraction: float = 0.2, rel_tol: float = 1e-3
) -> bool:
    """True if the best-so-far value stopped improving.

    ``trajectory`` holds the best-so-far objective (to be minimised, e.g. energy) per
    iteration. Plateau: over the last ``window_fraction`` of iterations the improvement is
    at most ``rel_tol * |final value|``.
    """
    n = len(trajectory)
    if n < 2:
        return False
    start = max(0, n - max(1, int(math.ceil(window_fraction * n))) - 1)
    improvement = float(trajectory[start] - trajectory[-1])
    scale = max(abs(float(trajectory[-1])), 1e-12)
    return improvement <= rel_tol * scale
