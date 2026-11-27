"""Optics, transmission-matrix models, Ising energy and metrics (small N, fixed seeds)."""

import math

import numpy as np
import pytest

from experimental_system.scientific_core import geometry, ising, metrics, optics, transmission


@pytest.fixture
def rng() -> np.random.Generator:
    return np.random.default_rng(1234)


def _random_spins(rng: np.random.Generator, shape: tuple[int, ...]) -> np.typing.NDArray[np.int8]:
    return rng.choice(np.array([-1, 1], dtype=np.int8), size=shape)


def test_spin_phase_encoding() -> None:
    spins = np.array([1, -1, 1], dtype=np.int8)
    phases = optics.spins_to_phases(spins)
    assert np.allclose(phases, [0.0, np.pi, 0.0])
    assert np.allclose(optics.phase_field(phases), spins)


def test_utc_normalisation(rng: np.random.Generator) -> None:
    tm = transmission.utc_matrix(64, 64, rng)
    phases = rng.uniform(0, 2 * np.pi, size=(400, 64))
    mean_intensity = optics.intensity(optics.propagate(tm, optics.phase_field(phases))).mean()
    assert mean_intensity == pytest.approx(1.0, rel=0.1)


def test_propagate_single_and_batch_agree(rng: np.random.Generator) -> None:
    tm = transmission.utc_matrix(9, 16, rng)
    fields = optics.phase_field(rng.uniform(0, 2 * np.pi, size=(3, 16)))
    batch = optics.propagate(tm, fields)
    assert batch.shape == (3, 9)
    assert np.allclose(batch[1], optics.propagate(tm, fields[1]))


@pytest.mark.parametrize("targets", [[0], [3, 7]])
def test_optical_energy_equals_coupling_energy(
    rng: np.random.Generator, targets: list[int]
) -> None:
    """Mandatory test: H computed optically through T equals H computed through J."""
    tm = transmission.utc_matrix(16, 16, rng)
    coupling = ising.coupling_matrix(tm, targets)
    assert np.allclose(coupling, coupling.T)
    spins = _random_spins(rng, (50, 16))
    assert np.allclose(ising.energy_optical(tm, targets, spins), ising.energy(coupling, spins))


def test_energy_is_flip_symmetric(rng: np.random.Generator) -> None:
    tm = transmission.utc_matrix(4, 10, rng)
    coupling = ising.coupling_matrix(tm, [1])
    spins = _random_spins(rng, (10,))
    assert ising.energy(coupling, spins) == pytest.approx(ising.energy(coupling, -spins))


def test_exact_ground_state_matches_naive_enumeration(rng: np.random.Generator) -> None:
    tm = transmission.utc_matrix(4, 8, rng)
    coupling = ising.coupling_matrix(tm, [0, 2])
    e_min, best = ising.exact_ground_state(coupling, chunk=7)  # small chunks on purpose
    all_spins = np.array(
        [[1 - 2 * ((k >> b) & 1) for b in range(8)] for k in range(256)], dtype=np.int8
    )
    assert e_min == pytest.approx(ising.energy(coupling, all_spins).min())
    assert float(ising.energy(coupling, best)) == pytest.approx(e_min)
    assert best[0] == 1


def test_exact_ground_state_size_limit() -> None:
    with pytest.raises(ValueError):
        ising.exact_ground_state(np.zeros((21, 21)))


def test_single_target_ground_state_is_mattis_like(rng: np.random.Generator) -> None:
    """One target mode: J is rank one; the ground state beats random configurations."""
    tm = transmission.utc_matrix(1, 12, rng)
    coupling = ising.coupling_matrix(tm, [0])
    assert np.linalg.matrix_rank(coupling) <= 2
    e_min, _ = ising.exact_ground_state(coupling)
    assert e_min <= ising.energy(coupling, _random_spins(rng, (200, 12))).min()


def test_gap_magnetization_overlap() -> None:
    assert ising.relative_energy_gap(-9.0, -10.0) == pytest.approx(0.1)
    up = np.ones(4, dtype=np.int8)
    mixed = np.array([1, 1, -1, -1], dtype=np.int8)
    assert ising.magnetization(-up) == 1.0
    assert ising.magnetization(mixed) == 0.0
    assert ising.overlap(up, -up) == -1.0
    assert ising.overlap(up, mixed) == 0.0
    mask = np.array([True, True, False, False])
    assert ising.overlap(up, mixed, mask) == 1.0
    replicas = np.stack([up, -up, mixed])
    assert np.allclose(ising.replica_overlaps(replicas), [1.0, 0.0, 0.0])


def test_target_modes() -> None:
    assert geometry.target_modes(8, 8, 1, 0.0) == [geometry.target_modes(8, 8, 1, 0.0)[0]]
    a, b = geometry.target_modes(8, 8, 2, 4.0)
    pos = geometry.camera_positions(8, 8)
    assert np.linalg.norm(pos[a] - pos[b]) == pytest.approx(4.0)
    a0, b0 = geometry.target_modes(8, 8, 2, 0.0)  # same point -> neighbouring mode
    assert a0 != b0


def test_thin_scatterer_locality(rng: np.random.Generator) -> None:
    g = transmission.circular_gaussian((64, 64), rng)
    narrow = transmission.thin_scatterer_matrix(g, 8, 8, ell=0.7)
    wide = transmission.thin_scatterer_matrix(g, 8, 8, ell=3.0)
    target = geometry.target_modes(8, 8, 1, 0.0)
    roi_narrow = ising.region_of_interest(narrow, target).sum()
    roi_wide = ising.region_of_interest(wide, target).sum()
    assert roi_narrow < roi_wide
    # rows normalised: every mode receives total power ~ sum_i |t_mi|^2 of order 1
    assert np.abs(narrow).max() > np.abs(wide).max()
    assert np.allclose((np.abs(narrow) ** 2).sum(axis=1).mean(), 1.0, rtol=0.3)


def test_camera_quantisation_and_saturation(rng: np.random.Generator) -> None:
    camera = optics.CameraModel(gain=1.0, read_noise=0.0, shot_noise=0.0)
    frame = camera.capture(np.array([10.0, 300.0, -1.0]), 1.0, 1.0, rng)
    assert frame.dtype == np.uint8
    assert frame.tolist() == [10, 255, 0]
    assert optics.saturation_fraction(frame) == pytest.approx(1 / 3)
    doubled = camera.capture(np.array([10.0]), 1.0, 2.0, rng)
    assert doubled.tolist() == [20]


def test_quantize_phases() -> None:
    q = optics.quantize_phases(np.array([-0.01, 2 * np.pi - 0.001, np.pi]), 4)
    assert np.allclose(q, [0.0, 0.0, np.pi])


def test_row_correlation_is_phase_invariant(rng: np.random.Generator) -> None:
    tm = transmission.utc_matrix(5, 16, rng)
    phases = np.exp(1j * rng.uniform(0, 2 * np.pi, size=(5, 1)))
    assert np.allclose(metrics.row_correlations(tm * phases * 3.0, tm), 1.0)
    other = transmission.utc_matrix(5, 16, rng)
    assert metrics.row_correlations(other, tm).mean() < 0.6


def test_enhancement_theory() -> None:
    assert metrics.theoretical_enhancement_phase_only(1) == 1.0
    assert metrics.theoretical_enhancement_phase_only(65) == pytest.approx(math.pi / 4 * 64 + 1)
    assert metrics.theoretical_enhancement_phase_only(65, 2) == pytest.approx(math.pi / 8 * 64 + 1)
    assert metrics.enhancement(50.0, 2.0) == 25.0
    with pytest.raises(ValueError):
        metrics.enhancement(1.0, 0.0)


def test_phase_conjugation_reaches_theoretical_enhancement(rng: np.random.Generator) -> None:
    """With the true T, continuous phase conjugation gives eta close to pi/4 (N-1) + 1."""
    n = 256
    values = []
    for _ in range(5):
        tm = transmission.utc_matrix(4, n, rng)
        mask = optics.phase_field(-np.angle(tm[0]))
        focus = optics.intensity(optics.propagate(tm, mask))[0]
        values.append(focus)  # reference <I> = 1 by normalisation
    eta = float(np.mean(values))
    assert eta == pytest.approx(metrics.theoretical_enhancement_phase_only(n), rel=0.15)


def test_plateau_detection() -> None:
    flat = np.concatenate([np.linspace(0, -10, 50), np.full(50, -10.0)])
    falling = np.linspace(0, -10, 100)
    assert metrics.has_plateau(flat)
    assert not metrics.has_plateau(falling)
    assert not metrics.has_plateau(np.array([1.0]))
