import json
from pathlib import Path

import pytest

from pithos_contracts import ValidationFailure, validate_document, validate_events, validate_report


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "contracts" / "fixtures"


@pytest.mark.parametrize(
    ("schema_name", "fixture_name"),
    [
        ("run", "run.json"),
        ("micro-rush", "micro-rush.json"),
    ],
)
def test_valid_json_documents(schema_name, fixture_name):
    document = json.loads((FIXTURES / "valid" / fixture_name).read_text())

    validate_document(document, schema_name)


def test_valid_event_stream():
    event_count = validate_events(FIXTURES / "valid" / "events.jsonl")

    assert event_count == 2


def test_valid_report():
    validate_report(FIXTURES / "valid" / "report.md")


@pytest.mark.parametrize(
    "fixture_name",
    [
        "event-missing-payload.jsonl",
        "event-bad-timestamp.jsonl",
    ],
)
def test_invalid_event_streams(fixture_name):
    with pytest.raises(ValidationFailure, match="line 1"):
        validate_events(FIXTURES / "invalid" / fixture_name)


def test_invalid_run_status():
    document = json.loads((FIXTURES / "invalid" / "run-bad-status.json").read_text())

    with pytest.raises(ValidationFailure, match="successful"):
        validate_document(document, "run")


def test_report_requires_all_sections():
    with pytest.raises(ValidationFailure, match="Next items"):
        validate_report(FIXTURES / "invalid" / "report-missing-section.md")


def test_report_requires_section_order(tmp_path):
    valid_report = (FIXTURES / "valid" / "report.md").read_text()
    reordered_report = valid_report.replace("## Work", "## Temporary").replace("## Context", "## Work")
    reordered_report = reordered_report.replace("## Temporary", "## Context")
    report_path = tmp_path / "report.md"
    report_path.write_text(reordered_report)

    with pytest.raises(ValidationFailure, match="ordered"):
        validate_report(report_path)

