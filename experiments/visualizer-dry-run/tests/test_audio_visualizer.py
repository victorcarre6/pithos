"""Executable acceptance checks for the scalar FFT band contract."""

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.audio_visualizer import split_bands


assert split_bands([]) == (0.0, 0.0, 0.0)
assert split_bands([0.0] * 9) == (0.0, 0.0, 0.0)
assert split_bands([1.0] * 9) == (1.0, 1.0, 1.0)
assert split_bands([1.0] * 3 + [0.0] * 6) == (1.0, 0.0, 0.0)
assert split_bands([0.0] * 3 + [1.0] * 3 + [0.0] * 3) == (0.0, 1.0, 0.0)
assert split_bands([0.0] * 6 + [1.0] * 3) == (0.0, 0.0, 1.0)

print("project acceptance: PASS")
