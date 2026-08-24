#!/usr/bin/env python3
"""Harness-owned acceptance oracle for temporal band smoothing."""

import math
import subprocess
import sys
from pathlib import Path


sys.path.insert(0, str(Path.cwd() / "src"))

from audio_visualizer import smooth_levels, split_bands


previous = (0.2, 0.4, 0.6)
current = (1.0, 0.0, 0.2)

assert smooth_levels(previous, current, 0.0) == previous
assert smooth_levels(previous, current, 1.0) == current
midpoint = smooth_levels(previous, current, 0.25)
assert isinstance(midpoint, tuple)
assert len(midpoint) == 3
assert all(math.isclose(value, expected) for value, expected in zip(midpoint, (0.4, 0.3, 0.5)))
assert split_bands([1.0] * 9) == (1.0, 1.0, 1.0)

project_tests = subprocess.run(
    [sys.executable, "tests/test_audio_visualizer.py"],
    cwd=Path.cwd(),
    capture_output=True,
    text=True,
    check=False,
)
if project_tests.returncode != 0:
    raise AssertionError(project_tests.stdout + project_tests.stderr)

print("visualizer smoothing acceptance: PASS")
