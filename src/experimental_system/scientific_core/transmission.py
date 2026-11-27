"""Transmission-matrix models for the simulated scattering medium.

T has shape (M, N): M camera modes x N SLM macro-pixels, ``E_out = T @ E_in``.
Normalisation: for a random-phase input every output mode has mean intensity ~1.
"""

import numpy as np

from experimental_system.scientific_core.geometry import (
    camera_positions,
    pairwise_distances,
    slm_positions,
)
from experimental_system.scientific_core.types import ComplexArray, FloatArray


def circular_gaussian(shape: tuple[int, int], rng: np.random.Generator) -> ComplexArray:
    """i.i.d. circular complex Gaussian entries with unit variance E|g|^2 = 1."""
    real = rng.standard_normal(shape)
    imag = rng.standard_normal(shape)
    return np.asarray((real + 1j * imag) / np.sqrt(2.0), dtype=np.complex128)


def utc_matrix(n_modes: int, n_pixels: int, rng: np.random.Generator) -> ComplexArray:
    """Uncorrelated transmission coefficient (UTC) model: thick scatterer, all-to-all.

    Entries are i.i.d. circular Gaussian with variance 1/N (Huang et al. 2021, Goodman).
    """
    return np.asarray(
        circular_gaussian((n_modes, n_pixels), rng) / np.sqrt(n_pixels), dtype=np.complex128
    )


def interaction_envelope(slm_side: int, camera_side: int, ell: float) -> FloatArray:
    """Amplitude envelope w_mi = exp(-d_mi^2 / (2 ell^2)) of a thin scatterer.

    d_mi is the distance between camera mode m and SLM pixel i (in macro-pixels). Light
    reaching mode m comes only from pixels within ~ell (Delloye et al. 2023, Fig. 1-2).
    """
    if ell <= 0:
        raise ValueError(f"interaction length must be > 0, got {ell}")
    d = pairwise_distances(camera_positions(camera_side, slm_side), slm_positions(slm_side))
    return np.exp(-(d**2) / (2.0 * ell**2))


def thin_scatterer_matrix(
    random_part: ComplexArray, slm_side: int, camera_side: int, ell: float
) -> ComplexArray:
    """Thin scatterer with finite interaction length ``ell``: T = g ⊙ w, row-normalised.

    ``random_part`` (unit-variance circular Gaussian, shape (M, N)) is the fixed microscopic
    disorder of the medium; changing ``ell`` changes only the envelope, so the same medium
    is described consistently at different settings. Each row is divided by
    sqrt(sum_i w_mi^2) so that every mode keeps mean intensity ~1.
    """
    w = interaction_envelope(slm_side, camera_side, ell)
    if random_part.shape != w.shape:
        raise ValueError(f"random_part shape {random_part.shape} != envelope {w.shape}")
    norm = np.sqrt((w**2).sum(axis=1, keepdims=True))
    return (random_part * w / norm).astype(np.complex128)
