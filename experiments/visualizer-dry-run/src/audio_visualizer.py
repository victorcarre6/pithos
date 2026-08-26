"""FFT-based audio visualizer core for the VJing experiment.

Provides pure functions for deterministic audio analysis without I/O or
external dependencies.
"""

import cmath
import math


def split_bands(magnitudes: list[float]) -> tuple[float, float, float]:
    """Split an FFT magnitude spectrum into bass, mid, and treble bands.

    Parameters
    ----------
    magnitudes : list[float]
        Non-negative FFT magnitude values (one per FFT bin).  Empty list
        returns three zeroes.

    Returns
    -------
    tuple[float, float, float]
        (bass, mid, treble) — three scalar floats, each in [0, 1].

    The split is based on linear positional tripartition: the first third
    (indices 0..N//3) maps to bass, the second third (indices N//3..2N//3)
    to mid, and the last third (indices 2N//3..N) to treble.  Every original
    position is assigned to exactly one band.  Each band element is the mean
    of its tranche.  The returned values are the arithmetic means of the
    respective tranches.

    Note:
        This is a pure function.  It returns three scalar floats.
    """
    if not magnitudes:
        return 0.0, 0.0, 0.0

    n = len(magnitudes)
    third = n // 3

    bass_mean = sum(magnitudes[0:third]) / third if third else 0.0
    mid_mean = sum(magnitudes[third:2 * third]) / third if third else 0.0
    treble_mean = sum(magnitudes[2 * third:]) / (n - 2 * third) if n > 2 * third else 0.0

    return bass_mean, mid_mean, treble_mean


def compute_magnitudes(samples: list[float]) -> list[float]:
    """Return one DFT magnitude per real input sample."""

    sample_count = len(samples)
    magnitudes = []

    for frequency in range(sample_count):
        coefficient = 0j
        for sample_index, sample in enumerate(samples):
            angle = -2j * math.pi * frequency * sample_index / sample_count
            coefficient += sample * cmath.exp(angle)

        magnitude = abs(coefficient)
        magnitudes.append(magnitude)

    return magnitudes


def smooth_levels(previous: tuple[float, float, float], current: tuple[float, float, float], alpha: float) -> tuple[float, float, float]:
    """Smooth two level vectors using a weighted exponential blending.

    Each band is applied independently:
        smoothed[i] = previous[i] * (1 - alpha) + current[i] * alpha

    Parameters
    ----------
    previous : tuple[float, float, float]
        The previous (bass, mid, treble) levels.
    current : tuple[float, float, float]
        The current (bass, mid, treble) levels.
    alpha : float
        Blend weight in (0.0, 1.0).

    Returns
    -------
    tuple[float, float, float]
        The smoothed (bass, mid, treble) levels.
    """
    return (
        previous[0] * (1 - alpha) + current[0] * alpha,
        previous[1] * (1 - alpha) + current[1] * alpha,
        previous[2] * (1 - alpha) + current[2] * alpha,
    )


def clamp_levels(levels: tuple[float, float, float]) -> tuple[float, float, float]:
    """Clamp each band level to the range [0, 1].

    Parameters
    ----------
    levels : tuple[float, float, float]
        A triplet (bass, mid, treble) of floats.

    Returns
    -------
    tuple[float, float, float]
        A triplet where each element is clamped to [0, 1].
    """
    return (
        max(0.0, min(1.0, levels[0])),
        max(0.0, min(1.0, levels[1])),
        max(0.0, min(1.0, levels[2])),
    )


def process_frame(previous: tuple[float, float, float], magnitudes: list[float], alpha: float) -> tuple[float, float, float]:
    """Process a frame: split, smooth, and clamp FFT magnitude bands.

    Parameters
    ----------
    previous : tuple[float, float, float]
        The previous (bass, mid, treble) levels.
    magnitudes : list[float]
        Non-negative FFT magnitude values.
    alpha : float
        Blend weight in (0.0, 1.0).

    Returns
    -------
    tuple[float, float, float]
        The resulting (bass, mid, treble) triplet.
    """
    current = split_bands(magnitudes)
    smoothed = smooth_levels(previous, current, alpha)
    return clamp_levels(smoothed)
