#!/usr/bin/env python3
"""Harness-owned acceptance oracle for real-signal DFT magnitudes."""

import math
import subprocess
import sys
from pathlib import Path


sys.path.insert(0, str(Path.cwd() / "src"))

from audio_visualizer import compute_magnitudes


def _close(actual, expected):
    return len(actual) == len(expected) and all(math.isclose(a, e, abs_tol=1e-9) for a, e in zip(actual, expected))


assert compute_magnitudes([]) == []
assert _close(compute_magnitudes([0.0, 0.0, 0.0, 0.0]), [0.0, 0.0, 0.0, 0.0])
assert _close(compute_magnitudes([2.0, 2.0, 2.0, 2.0]), [8.0, 0.0, 0.0, 0.0])

project_tests = subprocess.run(
    [sys.executable, "tests/test_audio_visualizer.py"],
    cwd=Path.cwd(),
    capture_output=True,
    text=True,
    check=False,
)
if project_tests.returncode != 0:
    raise AssertionError(project_tests.stdout + project_tests.stderr)

print("visualizer magnitudes acceptance: PASS")
