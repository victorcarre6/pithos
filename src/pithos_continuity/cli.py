"""CLI for publishing and inspecting the global continuity report."""

import argparse
from pathlib import Path

from pithos_contracts import ValidationFailure

from .reports import ContinuityError, load_latest_report, publish_report


def main() -> int:
    """Execute one continuity operation with shell-friendly errors."""

    parser = argparse.ArgumentParser(description="Manage the Pithos continuity report")
    parser.add_argument("--logs-root", type=Path, default=Path.home() / "logs" / "pithos")
    subparsers = parser.add_subparsers(dest="command", required=True)

    publish_parser = subparsers.add_parser("publish")
    publish_parser.add_argument("report", type=Path)
    subparsers.add_parser("latest")
    arguments = parser.parse_args()

    try:
        if arguments.command == "publish":
            archive_path = publish_report(arguments.report, arguments.logs_root)
            print(f"Published {archive_path}")
        else:
            metadata, content = load_latest_report(arguments.logs_root)
            print(f"run_id={metadata['run_id']}")
            print(content)
    except (OSError, ValidationFailure, ContinuityError) as error:
        print(f"Continuity error: {error}")

        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

