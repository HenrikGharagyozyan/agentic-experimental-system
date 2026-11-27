"""Optical forward model: phase-only SLM -> transmission matrix -> intensity camera."""

from dataclasses import dataclass

import numpy as np

from experimental_system.scientific_core.types import (
    ComplexArray,
    CountsArray,
    FloatArray,
    SpinArray,
)

TWO_PI = 2.0 * np.pi
CAMERA_MAX_COUNTS = 255  # mono8


def spins_to_phases(spins: SpinArray) -> FloatArray:
    """Binary phase encoding of spins: +1 -> 0, -1 -> pi (Delloye et al.)."""
    return np.where(spins > 0, 0.0, np.pi).astype(np.float64)


def phase_field(phases: FloatArray) -> ComplexArray:
    """Unit-amplitude input field exp(i*phi). Works for (N,) and batches (L, N)."""
    return np.exp(1j * phases).astype(np.complex128)


def quantize_phases(phases: FloatArray, levels: int) -> FloatArray:
    """Wrap to [0, 2pi) and round to ``levels`` equally spaced SLM phase levels."""
    if levels < 2:
        raise ValueError("levels must be >= 2")
    step = TWO_PI / levels
    wrapped = np.mod(phases, TWO_PI)
    return np.mod(np.round(wrapped / step) * step, TWO_PI).astype(np.float64)


def propagate(tm: ComplexArray, fields: ComplexArray) -> ComplexArray:
    """Output field E_out = T @ E_in. ``fields`` is (N,) or a batch (L, N) -> (L, M)."""
    if fields.ndim == 1:
        return (tm @ fields).astype(np.complex128)
    return (fields @ tm.T).astype(np.complex128)


def intensity(field: ComplexArray) -> FloatArray:
    """I = |E|^2."""
    return (np.abs(field) ** 2).astype(np.float64)


@dataclass(frozen=True)
class CameraModel:
    """8-bit camera: counts = clip(round(gain * power * exposure * I + noise), 0, 255).

    ``gain`` is in counts / (mW * ms * unit intensity). Noise = Gaussian read noise plus
    shot-like noise with variance ``shot_noise * signal`` (both in counts).
    """

    gain: float = 2.0
    read_noise: float = 0.5
    shot_noise: float = 0.5

    def expected_counts(self, light: FloatArray, power_mw: float, exposure_ms: float) -> FloatArray:
        """Noise-free, unclipped signal in counts."""
        return (self.gain * power_mw * exposure_ms * light).astype(np.float64)

    def capture(
        self,
        light: FloatArray,
        power_mw: float,
        exposure_ms: float,
        rng: np.random.Generator,
    ) -> CountsArray:
        signal = self.expected_counts(light, power_mw, exposure_ms)
        sigma = np.sqrt(self.read_noise**2 + self.shot_noise * np.maximum(signal, 0.0))
        noisy = signal + sigma * rng.standard_normal(signal.shape)
        return np.clip(np.round(noisy), 0, CAMERA_MAX_COUNTS).astype(np.uint8)


def saturation_fraction(frame: CountsArray) -> float:
    """Fraction of pixels at the 255-count ceiling."""
    return float(np.mean(frame >= CAMERA_MAX_COUNTS)) if frame.size else 0.0
