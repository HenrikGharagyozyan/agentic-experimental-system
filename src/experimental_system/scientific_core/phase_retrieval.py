"""Phase retrieval: Generalized Gerchberg-Saxton (TM calibration) and classical GS.

References
- Huang et al., "Generalizing the Gerchberg-Saxton algorithm for retrieving complex optical
  transmission matrices", Photonics Research 9(1), 2021  -> ``generalized_gs``.
- Zhao & Chi, "Modified Gerchberg-Saxton (G-S) Algorithm and Its Application", Entropy 22,
  2020 -> ``gerchberg_saxton`` with ``FourierPropagator`` (classical GS) or
  ``FresnelPropagator`` (their single-phase retrieval, SPR).

TODO(later): DPR / MPR (Zhao & Chi, Sec. 3.2-3.3) retrieve 2..n cascaded phase masks in
different Fresnel planes. Our setup has one SLM plane, so they do not fit the single-mask
interface below; add a ``CascadePropagator`` if a multi-plane setup appears.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

import numpy as np

from experimental_system.scientific_core.types import ComplexArray, FloatArray

GGSAlgorithm = Literal["ggs_1", "ggs_2", "ggs_2_1"]

# Exponent schedule of |E|^n per stage (Huang et al.: GGS 2-1 = n=2, then n=1).
GGS_SCHEDULES: dict[GGSAlgorithm, tuple[float, ...]] = {
    "ggs_1": (1.0,),
    "ggs_2": (2.0,),
    "ggs_2_1": (2.0, 1.0),
}
GGS_TOLERANCE = 0.999999  # row correlation between X_f and X_{f-2}
GGS_MAX_ITERATIONS = 1000


# --- Generalized GS (transmission-matrix retrieval) -----------------------------------------


@dataclass(frozen=True)
class GGSResult:
    tm: ComplexArray  # (M, N), each row known up to a global phase
    iterations: tuple[int, ...]  # iterations used per stage
    converged_fraction: float  # rows that met the tolerance in the last stage


def _row_correlation(a: ComplexArray, b: ComplexArray) -> FloatArray:
    inner = np.abs(np.sum(np.conj(a) * b, axis=1))
    norms = np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1)
    return np.asarray(inner / np.where(norms > 0, norms, np.inf), dtype=np.float64)


def generalized_gs(
    probes: ComplexArray,
    amplitudes: FloatArray,
    *,
    algorithm: GGSAlgorithm = "ggs_2_1",
    max_iterations: int = GGS_MAX_ITERATIONS,
    tolerance: float = GGS_TOLERANCE,
    rng: np.random.Generator,
) -> GGSResult:
    """Retrieve T (M x N) from probe masks P (L x N) and measured amplitudes |E| (L x M).

    Iteration f (Huang et al., Eqs. 3-4), with X_f the current estimate of T:
        E_f = |E|^n ⊙ exp(i Arg(P X_{f-1}^T)),   X_f = (P^+ E_f)^T
    A row stops when corr(X_f, X_{f-2}) > tolerance (the f-2 comparison avoids the
    period-2 oscillation noted in the paper); converged rows leave the iteration.
    """
    n_probes, n_pixels = probes.shape
    if amplitudes.shape[0] != n_probes:
        raise ValueError("amplitudes must have one row per probe mask")
    n_modes = amplitudes.shape[1]
    pinv = np.linalg.pinv(probes)  # (N, L)
    real = rng.standard_normal((n_modes, n_pixels))
    imag = rng.standard_normal((n_modes, n_pixels))
    estimate = np.asarray(real + 1j * imag, dtype=np.complex128)

    used: list[int] = []
    converged = np.zeros(n_modes, dtype=bool)
    for exponent in GGS_SCHEDULES[algorithm]:
        target = amplitudes**exponent  # (L, M)
        converged = np.zeros(n_modes, dtype=bool)
        older = estimate.copy()  # X_{f-2}
        old = estimate.copy()  # X_{f-1}
        iteration = 0
        while iteration < max_iterations and not converged.all():
            iteration += 1
            active = np.flatnonzero(~converged)
            predicted = probes @ old[active].T  # (L, A)
            field = target[:, active] * np.exp(1j * np.angle(predicted))
            new = (pinv @ field).T  # (A, N)
            done = _row_correlation(new, older[active]) > tolerance
            estimate[active] = new
            converged[active[done]] = True
            older[active] = old[active]
            old[active] = new
        used.append(iteration)
    return GGSResult(
        tm=estimate,
        iterations=tuple(used),
        converged_fraction=float(converged.mean()),
    )


def random_phase_probes(n_probes: int, n_pixels: int, rng: np.random.Generator) -> FloatArray:
    """Phases theta in [0, 2pi) of L random phase-only probe masks (L x N)."""
    return rng.uniform(0.0, 2.0 * np.pi, size=(n_probes, n_pixels))


def focusing_phases(tm_estimate: ComplexArray, targets: Sequence[int]) -> FloatArray:
    """Phase conjugation: phi_i = -Arg(x_mi) for one target mode m.

    Several targets: phi_i = -Arg(sum_{m in S} x_mi). Each retrieved row carries an unknown
    global phase, so the foci get random relative phases - irrelevant for intensity foci.
    """
    combined = tm_estimate[list(targets), :].sum(axis=0)
    return np.asarray(-np.angle(combined), dtype=np.float64)


# --- Classical GS and variants over a common propagator interface ---------------------------


class Propagator(Protocol):
    """Linear map from the SLM plane to the detector plane, and its (pseudo-)inverse."""

    def forward(self, field: ComplexArray) -> ComplexArray: ...

    def backward(self, field: ComplexArray) -> ComplexArray: ...


class FourierPropagator:
    """Lens / far field: orthonormal 2-D FFT (classical GS)."""

    def forward(self, field: ComplexArray) -> ComplexArray:
        return np.asarray(np.fft.fft2(field, norm="ortho"), dtype=np.complex128)

    def backward(self, field: ComplexArray) -> ComplexArray:
        return np.asarray(np.fft.ifft2(field, norm="ortho"), dtype=np.complex128)


class FresnelPropagator:
    """Fresnel transform over distance z (transfer-function method), for SPR.

    H(fx, fy) = exp(-i pi lambda z (fx^2 + fy^2)) (constant phase exp(ikz) dropped: it
    does not change intensities). All lengths in metres.
    """

    def __init__(self, shape: tuple[int, int], wavelength: float, pitch: float, distance: float):
        fy = np.fft.fftfreq(shape[0], d=pitch)
        fx = np.fft.fftfreq(shape[1], d=pitch)
        fx2, fy2 = np.meshgrid(fx**2, fy**2)
        self._h = np.exp(-1j * np.pi * wavelength * distance * (fx2 + fy2))

    def forward(self, field: ComplexArray) -> ComplexArray:
        return np.asarray(np.fft.ifft2(np.fft.fft2(field) * self._h), dtype=np.complex128)

    def backward(self, field: ComplexArray) -> ComplexArray:
        return np.asarray(np.fft.ifft2(np.fft.fft2(field) * np.conj(self._h)), dtype=np.complex128)


class MatrixPropagator:
    """Known transmission matrix: forward T @ E, backward pinv(T) @ E (least squares)."""

    def __init__(self, tm: ComplexArray) -> None:
        self._tm = tm
        self._pinv = np.linalg.pinv(tm)

    def forward(self, field: ComplexArray) -> ComplexArray:
        return np.asarray(self._tm @ field, dtype=np.complex128)

    def backward(self, field: ComplexArray) -> ComplexArray:
        return np.asarray(self._pinv @ field, dtype=np.complex128)


@dataclass(frozen=True)
class GSResult:
    phases: FloatArray  # SLM phase mask, same shape as the source plane
    correlation: tuple[float, ...]  # CC(|output|, target) per iteration
    iterations: int


def correlation_coefficient(a: FloatArray, b: FloatArray) -> float:
    """Pearson correlation coefficient (the CC used by Zhao & Chi)."""
    x = a.ravel() - a.mean()
    y = b.ravel() - b.mean()
    denom = float(np.linalg.norm(x) * np.linalg.norm(y))
    return float(x @ y) / denom if denom > 0 else 0.0


def gerchberg_saxton(
    propagator: Propagator,
    source_amplitude: FloatArray,
    target_amplitude: FloatArray,
    *,
    n_iterations: int = 200,
    tolerance: float | None = None,
    rng: np.random.Generator,
) -> GSResult:
    """GS loop (Zhao & Chi, Eqs. 1-4): keep the phase, impose the known amplitude.

    Source plane: phase-only SLM, amplitude ``source_amplitude`` (ones for a uniform beam).
    Stops after ``n_iterations`` or when CC >= ``tolerance`` (if given).
    """
    phases = rng.uniform(-np.pi, np.pi, size=source_amplitude.shape)
    history: list[float] = []
    for _ in range(n_iterations):
        incident = np.asarray(source_amplitude * np.exp(1j * phases), dtype=np.complex128)
        out = propagator.forward(incident)
        history.append(correlation_coefficient(np.abs(out), target_amplitude))
        if tolerance is not None and history[-1] >= tolerance:
            break
        imposed = np.asarray(target_amplitude * np.exp(1j * np.angle(out)), dtype=np.complex128)
        back = propagator.backward(imposed)
        phases = np.angle(back)
    return GSResult(
        phases=np.asarray(np.mod(phases, 2 * np.pi), dtype=np.float64),
        correlation=tuple(history),
        iterations=len(history),
    )


def single_phase_retrieval(
    target_amplitude: FloatArray,
    *,
    wavelength: float,
    pitch: float,
    distance: float,
    n_iterations: int = 200,
    rng: np.random.Generator,
) -> GSResult:
    """SPR (Zhao & Chi, Sec. 3.1): GS with a Fresnel transform instead of a Fourier one."""
    shape = (int(target_amplitude.shape[0]), int(target_amplitude.shape[1]))
    propagator = FresnelPropagator(shape, wavelength, pitch, distance)
    source = np.ones_like(target_amplitude, dtype=np.float64)
    return gerchberg_saxton(
        propagator, source, target_amplitude, n_iterations=n_iterations, rng=rng
    )
