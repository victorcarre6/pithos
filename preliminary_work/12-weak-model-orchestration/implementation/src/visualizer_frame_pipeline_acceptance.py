#!/usr/bin/env python3
"""Harness-owned acceptance oracle for the split -> smooth -> clamp frame pipeline."""

import math
import subprocess
import sys
from pathlib import Path


sys.path.insert(0, str(Path.cwd() / "src"))

from audio_visualizer import process_frame


def _close(actual, expected):
    return len(actual) == len(expected) and all(math.isclose(a, e, abs_tol=1e-9) for a, e in zip(actual, expected))


assert _close(process_frame((0.0, 0.0, 0.0), [], 0.0), (0.0, 0.0, 0.0))
assert _close(process_frame((1.0, 1.0, 1.0), [1.0] * 9, 1.0), (1.0, 1.0, 1.0))
assert _close(process_frame((0.2, 0.4, 0.6), [1.0] * 3 + [0.0] * 3 + [1.0] * 3, 0.5), (0.6, 0.2, 0.8))

project_tests = subprocess.run(
    [sys.executable, "tests/test_audio_visualizer.py"],
    cwd=Path.cwd(),
    capture_output=True,
    text=True,
    check=False,
)
if project_tests.returncode != 0:
    raise AssertionError(project_tests.stdout + project_tests.stderr)

print("visualizer frame-pipeline acceptance: PASS")
