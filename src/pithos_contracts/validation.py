"""Validation functions for Pithos JSON and Markdown contracts."""

import json
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker


SCHEMA_DIR = Path(__file__).resolve().parents[2] / "contracts" / "v1"
REPORT_SECTIONS = ("Context", "Work", "Next items")


class ValidationFailure(ValueError):
    """Report a contract violation with a stable human-readable message."""


def _load_schema(name: str) -> dict:
    schema_path = SCHEMA_DIR / f"{name}.schema.json"

    with schema_path.open(encoding="utf-8") as schema_file:
        return json.load(schema_file)


def validate_document(document: object, schema_name: str) -> None:
    """Validate a decoded JSON document against a named Pithos schema."""

    schema = _load_schema(schema_name)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(document), key=lambda error: list(error.absolute_path))

    if not errors:
        return

    first_error = errors[0]
    location = ".".join(str(part) for part in first_error.absolute_path)
    prefix = f"{location}: " if location else ""

    raise ValidationFailure(f"{prefix}{first_error.message}")


def validate_events(path: Path) -> int:
    """Validate every non-empty line of an append-only event stream."""

    event_count = 0

    with path.open(encoding="utf-8") as event_file:
        for line_number, raw_line in enumerate(event_file, start=1):
            line = raw_line.strip()
            if not line:
                continue

            try:
                event = json.loads(line)
                validate_document(event, "event")
            except (json.JSONDecodeError, ValidationFailure) as error:
                raise ValidationFailure(f"line {line_number}: {error}") from error

            event_count += 1

    if event_count == 0:
        raise ValidationFailure("event stream is empty")

    return event_count


def _split_frontmatter(content: str) -> tuple[dict, str]:
    lines = content.splitlines()
    if not lines or lines[0] != "---":
        raise ValidationFailure("report must start with YAML frontmatter")

    try:
        closing_index = lines[1:].index("---") + 1
    except ValueError as error:
        raise ValidationFailure("report frontmatter is not closed") from error

    metadata = yaml.safe_load("\n".join(lines[1:closing_index]))
    if not isinstance(metadata, dict):
        raise ValidationFailure("report frontmatter must decode to an object")

    body = "\n".join(lines[closing_index + 1 :])

    return metadata, body


def validate_report(path: Path) -> None:
    """Validate report metadata and the three required continuity sections."""

    content = path.read_text(encoding="utf-8")
    metadata, body = _split_frontmatter(content)
    validate_document(metadata, "report-metadata")

    section_positions = []
    for section in REPORT_SECTIONS:
        heading = f"## {section}"
        occurrences = body.count(heading)
        if occurrences != 1:
            raise ValidationFailure(f"report must contain exactly one {heading!r} heading")

        section_positions.append(body.index(heading))

    if section_positions != sorted(section_positions):
        raise ValidationFailure("report sections must be ordered Context, Work, Next items")

