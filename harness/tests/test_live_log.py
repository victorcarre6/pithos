import re
from concurrent.futures import ThreadPoolExecutor

import pytest

from pithos_live_log import LiveLog
from pithos_runner.events import EventWriter


RUN_ID = "run-20260823T120000Z-a1b2c3"


def test_line_is_identifiable_flushed_and_single_line(tmp_path):
    logger = LiveLog(tmp_path)

    returned = logger.write(RUN_ID, "WARNING", "runner", "first\nsecond")
    content = (tmp_path / "live.log").read_text()

    assert returned + "\n" == content
    assert re.match(r"^\d{4}-\d{2}-\d{2}T.* \[WARNING\] \[run-.*\] \[runner\]", content)
    assert "first\\nsecond" in content
    assert content.count("\n") == 1


def test_concurrent_writers_never_interleave_lines(tmp_path):
    logger = LiveLog(tmp_path)

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(lambda number: logger.write(RUN_ID, "INFO", "test", f"line-{number}"), range(100)))

    lines = (tmp_path / "live.log").read_text().splitlines()
    assert len(lines) == 100
    assert {line.rsplit(" ", 1)[-1] for line in lines} == {f"line-{number}" for number in range(100)}


def test_rotation_preserves_archive_and_continues_at_canonical_path(tmp_path):
    logger = LiveLog(tmp_path, rotate_bytes=100)
    logger.write(RUN_ID, "INFO", "test", "before rotation")
    logger.write(RUN_ID, "INFO", "test", "after rotation")

    archives = list((tmp_path / "archive" / "live").glob("live-*.log"))
    assert len(archives) == 1
    assert "before rotation" in archives[0].read_text()
    assert "after rotation" in (tmp_path / "live.log").read_text()


def test_restart_appends_without_overwriting(tmp_path):
    LiveLog(tmp_path).write(RUN_ID, "INFO", "one", "before")
    LiveLog(tmp_path).write(RUN_ID, "INFO", "two", "after")

    content = (tmp_path / "live.log").read_text()
    assert "before" in content
    assert "after" in content


def test_event_writer_mirrors_run_and_mission_events_without_sqlite_or_dashboard(tmp_path):
    run_events = tmp_path / "runs" / RUN_ID / "events.jsonl"
    mission_events = tmp_path / "missions" / RUN_ID / "events.jsonl"

    EventWriter(run_events, RUN_ID).append("run.started", {})
    EventWriter(mission_events, RUN_ID).append("run.finished", {"status": "completed"})

    live_log = (tmp_path / "live.log").read_text()
    assert "run.started" in live_log
    assert "run.finished" in live_log


def test_unknown_level_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="unsupported"):
        LiveLog(tmp_path).write(RUN_ID, "NOTICE", "test", "message")
