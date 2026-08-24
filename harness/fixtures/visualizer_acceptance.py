#!/usr/bin/env python3
"""Harness-owned acceptance oracle for the first visualizer micro-rush."""

import sys
import subprocess
from pathlib import Path


sys.path.insert(0, str(Path.cwd() / "src"))

from audio_visualizer import split_bands


def levels(magnitudes):
    result = split_bands(magnitudes)
    if isinstance(result, dict):
        values = [result.get("bass"), result.get("mid"), result.get("treble")]
    else:
        values = list(result)
    if len(values) != 3 or not all(isinstance(value, (int, float)) for value in values):
        raise AssertionError("split_bands must return exactly three scalar values: bass, mid, treble")

    return values


assert levels([0.0] * 9) == [0.0, 0.0, 0.0]
assert levels([1.0] * 9) == [1.0, 1.0, 1.0]
assert levels([1.0] * 3 + [0.0] * 6) == [1.0, 0.0, 0.0]
assert levels([0.0] * 3 + [1.0] * 3 + [0.0] * 3) == [0.0, 1.0, 0.0]
assert levels([0.0] * 6 + [1.0] * 3) == [0.0, 0.0, 1.0]

project_tests = subprocess.run(
    [sys.executable, "tests/test_audio_visualizer.py"],
    cwd=Path.cwd(),
    capture_output=True,
    text=True,
    check=False,
)
if project_tests.returncode != 0:
    raise AssertionError(project_tests.stdout + project_tests.stderr)

print("visualizer acceptance: PASS")
