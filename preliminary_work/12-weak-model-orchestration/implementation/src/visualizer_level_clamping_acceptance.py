#!/usr/bin/env python3
"""Harness-owned acceptance oracle for band-level clamping."""

import subprocess
import sys
from pathlib import Path


sys.path.insert(0, str(Path.cwd() / "src"))

from audio_visualizer import clamp_levels


assert clamp_levels((0.5, 0.5, 0.5)) == (0.5, 0.5, 0.5)
assert clamp_levels((0.0, 1.0, 0.0)) == (0.0, 1.0, 0.0)
assert clamp_levels((-0.2, 0.5, 1.3)) == (0.0, 0.5, 1.0)
assert clamp_levels((-5.0, 5.0, 0.0)) == (0.0, 1.0, 0.0)

project_tests = subprocess.run(
    [sys.executable, "tests/test_audio_visualizer.py"],
    cwd=Path.cwd(),
    capture_output=True,
    text=True,
    check=False,
)
if project_tests.returncode != 0:
    raise AssertionError(project_tests.stdout + project_tests.stderr)

print("visualizer level-clamping acceptance: PASS")
