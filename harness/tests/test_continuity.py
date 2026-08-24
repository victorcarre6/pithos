from pathlib import Path

import pytest

from pithos_continuity import ContinuityError, load_latest_report, publish_report
from pithos_continuity.probe import FACT, run_probe


ROOT = Path(__file__).resolve().parents[1]
VALID_REPORT = ROOT / "contracts" / "fixtures" / "valid" / "report.md"
INVALID_REPORT = ROOT / "contracts" / "fixtures" / "invalid" / "report-missing-section.md"


def test_publish_archives_and_updates_latest(tmp_path):
    archive_path = publish_report(VALID_REPORT, tmp_path)
    metadata, latest_content = load_latest_report(tmp_path)

    assert archive_path == tmp_path / "runs" / metadata["run_id"] / "report.md"
    assert archive_path.read_text() == latest_content
    assert metadata["micro_rush_id"] == "rush-audio-input"


def test_publish_is_idempotent_for_same_report(tmp_path):
    first_path = publish_report(VALID_REPORT, tmp_path)
    second_path = publish_report(VALID_REPORT, tmp_path)

    assert first_path == second_path


def test_publish_preserves_conflicting_archive(tmp_path):
    archive_path = publish_report(VALID_REPORT, tmp_path)
    archive_path.write_text("preserved failure artifact\n")

    with pytest.raises(ContinuityError, match="different content"):
        publish_report(VALID_REPORT, tmp_path)

    assert archive_path.read_text() == "preserved failure artifact\n"


def test_invalid_report_never_replaces_latest(tmp_path):
    publish_report(VALID_REPORT, tmp_path)
    previous_content = (tmp_path / "latest.md").read_text()

    with pytest.raises(ValueError):
        publish_report(INVALID_REPORT, tmp_path)

    assert (tmp_path / "latest.md").read_text() == previous_content


def test_absent_latest_is_explicit(tmp_path):
    with pytest.raises(ContinuityError, match="absent"):
        load_latest_report(tmp_path)


def test_probe_uses_two_independent_processes(tmp_path):
    fake_pi = tmp_path / "fake-pi"
    fake_pi.write_text(
        f"""#!/usr/bin/env python3
import json
import shutil
import sys
from pathlib import Path

prompt = sys.argv[-1]
if 'REPORT_TEMPLATE' in prompt:
    shutil.copy2('REPORT_TEMPLATE.md', 'report.md')
text = '{FACT}' if 'LATEST.md' in prompt and Path('LATEST.md').exists() else 'created'
for event in [
    {{'type': 'agent_start'}},
    {{'type': 'message_end', 'message': {{'role': 'assistant', 'content': [{{'type': 'text', 'text': text}}]}}}},
    {{'type': 'agent_end'}},
]:
    print(json.dumps(event))
"""
    )
    fake_pi.chmod(0o755)
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    result = run_probe(
        tmp_path / "probe",
        tmp_path / "logs",
        config_dir,
        "fake",
        2,
        str(fake_pi),
        "fake",
    )

    assert result["first_process_success"] is True
    assert result["second_process_success"] is True
    assert result["fact_recovered"] is True
    assert result["session_directories_distinct"] is True
