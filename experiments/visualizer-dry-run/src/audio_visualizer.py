"""FFT-based audio visualizer core for the VJing experiment.

Provides a pure function that splits an FFT magnitude spectrum into three
normalized bands: bass, mid, and treble.

Contract:
    split_bands(magnitudes: list[float]) -> tuple[float, float, float]

Each returned value is a scalar float in [0, 1].

Uses a linear cumulative-accumulation approach: the cumulative sum of magnitude
values is mapped into three bands (bass 0–20%, mid 20–60%, treble 60–100%).
"""


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
