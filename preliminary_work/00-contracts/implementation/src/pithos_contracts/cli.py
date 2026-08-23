"""Command-line validation for Pithos persistent artifacts."""

import argparse
import json
from pathlib import Path

from .validation import ValidationFailure, validate_document, validate_events, validate_report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate Pithos contracts")
    subparsers = parser.add_subparsers(dest="command", required=True)

    json_parser = subparsers.add_parser("json", help="validate one JSON document")
    json_parser.add_argument("schema", choices=("run", "micro-rush", "event", "report-metadata"))
    json_parser.add_argument("path", type=Path)

    events_parser = subparsers.add_parser("events", help="validate a JSONL event stream")
    events_parser.add_argument("path", type=Path)

    report_parser = subparsers.add_parser("report", help="validate a continuity report")
    report_parser.add_argument("path", type=Path)

    return parser


def main() -> int:
    """Validate the requested artifact and return a shell-friendly status."""

    arguments = _parser().parse_args()

    try:
        if arguments.command == "json":
            document = json.loads(arguments.path.read_text(encoding="utf-8"))
            validate_document(document, arguments.schema)
        elif arguments.command == "events":
            validate_events(arguments.path)
        else:
            validate_report(arguments.path)
    except (OSError, json.JSONDecodeError, ValidationFailure) as error:
        print(f"INVALID {arguments.path}: {error}")

        return 1

    print(f"VALID {arguments.path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

