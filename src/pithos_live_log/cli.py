"""Append a controlled line to the global live log."""

import argparse
from pathlib import Path

from .writer import LEVELS, LiveLog


def main() -> int:
    parser = argparse.ArgumentParser(description="Append one Pithos live log line")
    parser.add_argument("--logs-root", type=Path, default=Path.home() / "logs" / "pithos")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--level", choices=sorted(LEVELS), default="INFO")
    parser.add_argument("--component", required=True)
    parser.add_argument("message")
    arguments = parser.parse_args()
    line = LiveLog(arguments.logs_root.expanduser()).write(
        arguments.run_id,
        arguments.level,
        arguments.component,
        arguments.message,
    )
    print(line)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
