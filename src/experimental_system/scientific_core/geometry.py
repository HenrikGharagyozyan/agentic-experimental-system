"""Geometry of the (simulated) setup: SLM macro-pixel grid and camera mode grid.

Both grids are square and share one coordinate frame measured in SLM macro-pixels, so a
distance between an SLM pixel and a camera mode is meaningful (thin-scatterer model).
"""

import numpy as np

from experimental_system.scientific_core.types import FloatArray


def slm_positions(slm_side: int) -> FloatArray:
    """(N, 2) coordinates (row, col) of SLM macro-pixel centres, N = slm_side**2."""
    _check_side(slm_side)
    r, c = np.meshgrid(np.arange(slm_side), np.arange(slm_side), indexing="ij")
    return np.stack([r.ravel(), c.ravel()], axis=1).astype(np.float64)


def camera_positions(camera_side: int, slm_side: int) -> FloatArray:
    """(M, 2) coordinates of camera modes, spread over the same extent as the SLM grid."""
    _check_side(camera_side)
    _check_side(slm_side)
    axis = (np.arange(camera_side) + 0.5) * slm_side / camera_side - 0.5
    r, c = np.meshgrid(axis, axis, indexing="ij")
    return np.stack([r.ravel(), c.ravel()], axis=1).astype(np.float64)


def pairwise_distances(a: FloatArray, b: FloatArray) -> FloatArray:
    """(len(a), len(b)) Euclidean distances."""
    diff = a[:, None, :] - b[None, :, :]
    return np.sqrt((diff**2).sum(axis=-1))


def target_modes(camera_side: int, slm_side: int, n_targets: int, separation: float) -> list[int]:
    """Deterministic target camera modes.

    One target: the mode nearest the centre. Two targets: the modes nearest the points
    ``centre ± separation/2`` along the row axis (separation in SLM macro-pixels). If both
    points fall on the same mode, the second target is shifted by one mode.
    """
    if n_targets not in (1, 2):
        raise ValueError(f"n_targets must be 1 or 2, got {n_targets}")
    positions = camera_positions(camera_side, slm_side)
    centre = np.array([(slm_side - 1) / 2.0, (slm_side - 1) / 2.0])
    points = (
        [centre]
        if n_targets == 1
        else [
            centre - np.array([0.0, separation / 2.0]),
            centre + np.array([0.0, separation / 2.0]),
        ]
    )
    modes: list[int] = []
    for point in points:
        order = np.argsort(np.linalg.norm(positions - point, axis=1), kind="stable")
        mode = next(int(m) for m in order if int(m) not in modes)
        modes.append(mode)
    return modes


def _check_side(side: int) -> None:
    if side < 1:
        raise ValueError(f"grid side must be >= 1, got {side}")
