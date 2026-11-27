"""GGS (Huang et al. 2021) and GS / SPR (Zhao & Chi 2020) on small sizes, fixed seeds."""

import numpy as np
import pytest

from experimental_system.scientific_core import metrics, optics, transmission
from experimental_system.scientific_core import phase_retrieval as pr
from experimental_system.scientific_core.types import ComplexArray, FloatArray


def _calibration_data(
    n_pixels: int, n_modes: int, gamma: float, seed: int
) -> tuple[ComplexArray, ComplexArray, FloatArray, np.random.Generator]:
    rng = np.random.default_rng(seed)
    tm = transmission.utc_matrix(n_modes, n_pixels, rng)
    probes = optics.phase_field(pr.random_phase_probes(int(gamma * n_pixels), n_pixels, rng))
    amplitudes = np.abs(optics.propagate(tm, probes))
    return tm, probes, amplitudes, rng


@pytest.fixture(scope="module")
def ggs_results() -> dict[str, float]:
    """Mean row correlation with the true T for each GGS variant (N=64, M=16, gamma=4)."""
    out: dict[str, float] = {}
    algorithms: tuple[pr.GGSAlgorithm, ...] = ("ggs_1", "ggs_2", "ggs_2_1")
    for algorithm in algorithms:
        tm, probes, amplitudes, rng = _calibration_data(64, 16, 4.0, seed=7)
        result = pr.generalized_gs(probes, amplitudes, algorithm=algorithm, rng=rng)
        out[algorithm] = float(metrics.row_correlations(result.tm, tm).mean())
    return out


def test_ggs_2_1_retrieves_tm(ggs_results: dict[str, float]) -> None:
    assert ggs_results["ggs_2_1"] > 0.9


def test_ggs_variants_ranking_matches_paper(ggs_results: dict[str, float]) -> None:
    """Huang et al. Fig. 2a at gamma=4: GGS 2-1 > GGS 2 > GGS 1."""
    assert ggs_results["ggs_2_1"] > ggs_results["ggs_2"] > ggs_results["ggs_1"]


def test_ggs_focusing_close_to_theory() -> None:
    tm, probes, amplitudes, rng = _calibration_data(64, 8, 4.0, seed=11)
    result = pr.generalized_gs(probes, amplitudes, algorithm="ggs_2_1", rng=rng)
    assert len(result.iterations) == 2
    etas = []
    for mode in range(8):
        mask = optics.phase_field(pr.focusing_phases(result.tm, [mode]))
        etas.append(optics.intensity(optics.propagate(tm, mask))[mode])  # <I>_random = 1
    ratio = float(np.mean(etas)) / metrics.theoretical_enhancement_phase_only(64)
    assert ratio > 0.8


def test_ggs_respects_max_iterations() -> None:
    _, probes, amplitudes, rng = _calibration_data(16, 4, 4.0, seed=3)
    result = pr.generalized_gs(probes, amplitudes, algorithm="ggs_2", max_iterations=5, rng=rng)
    assert result.iterations == (5,)


def test_ggs_is_deterministic_for_seed() -> None:
    _, probes, amplitudes, _ = _calibration_data(16, 4, 4.0, seed=3)
    a = pr.generalized_gs(probes, amplitudes, rng=np.random.default_rng(0))
    b = pr.generalized_gs(probes, amplitudes, rng=np.random.default_rng(0))
    assert np.array_equal(a.tm, b.tm)


def test_ggs_rejects_inconsistent_shapes() -> None:
    _, probes, amplitudes, rng = _calibration_data(16, 4, 4.0, seed=3)
    with pytest.raises(ValueError):
        pr.generalized_gs(probes, amplitudes[:-1], rng=rng)


def _letter_target(size: int = 32) -> FloatArray:
    target = np.zeros((size, size))
    target[8:24, 10:13] = 1.0
    target[8:11, 10:22] = 1.0
    target[15:18, 10:19] = 1.0
    return target


def test_classical_gs_fourier() -> None:
    target = _letter_target()
    result = pr.gerchberg_saxton(
        pr.FourierPropagator(),
        np.ones_like(target),
        target,
        n_iterations=100,
        rng=np.random.default_rng(0),
    )
    assert result.correlation[-1] > 0.9
    assert result.correlation[-1] > result.correlation[0]
    assert result.phases.min() >= 0 and result.phases.max() < 2 * np.pi


def test_gs_stops_at_tolerance() -> None:
    target = _letter_target()
    result = pr.gerchberg_saxton(
        pr.FourierPropagator(),
        np.ones_like(target),
        target,
        n_iterations=500,
        tolerance=0.8,
        rng=np.random.default_rng(0),
    )
    assert result.iterations < 500
    assert result.correlation[-1] >= 0.8


def test_spr_fresnel() -> None:
    result = pr.single_phase_retrieval(
        _letter_target(),
        wavelength=532e-9,
        pitch=8e-6,
        distance=0.02,
        n_iterations=100,
        rng=np.random.default_rng(0),
    )
    assert result.correlation[-1] > 0.9


def test_fresnel_backward_inverts_forward() -> None:
    rng = np.random.default_rng(1)
    field = np.exp(1j * rng.uniform(0, 2 * np.pi, size=(16, 16)))
    prop = pr.FresnelPropagator((16, 16), 532e-9, 8e-6, 0.05)
    assert np.allclose(prop.backward(prop.forward(field)), field)


def test_gs_through_known_tm_makes_two_foci() -> None:
    rng = np.random.default_rng(5)
    tm = transmission.utc_matrix(16, 64, rng)
    target = np.zeros(16)
    target[[3, 12]] = 1.0
    result = pr.gerchberg_saxton(
        pr.MatrixPropagator(tm), np.ones(64), target, n_iterations=100, rng=rng
    )
    light = optics.intensity(optics.propagate(tm, optics.phase_field(result.phases)))
    others = np.delete(light, [3, 12])
    assert min(light[3], light[12]) > 5 * others.mean()
