#!/usr/bin/env python3
"""Run the complete deterministic acceptance suite for the visualizer."""

import subprocess
import sys


def main():
    """Execute every project validator and stop on the first failure."""

    commands = [
        [sys.executable, "tests/test_audio_visualizer.py"],
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests/test_start_visualizer.py"],
        ["node", "--test", "tests/test_web_audio.mjs"],
    ]

    for command in commands:
        result = subprocess.run(command, check=False)
        if result.returncode != 0:
            return result.returncode

    print("visualizer product acceptance: PASS")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
