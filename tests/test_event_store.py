import json
import sqlite3
from pathlib import Path

import pytest

from pithos_event_store import EventStore, IngestionError
from pithos_event_store.migrations import MIGRATIONS


RUN_ID = "run-20260823T120000Z-a1b2c3"


def _event(number, event_type, payload=None):
    return {
        "schema_version": "1.0",
        "event_id": f"evt-20260823T12000{number}.000000Z-a1b2c{number}",
        "run_id": RUN_ID,
        "timestamp": f"2026-08-23T12:00:0{number}+00:00",
        "type": event_type,
        "source": "test",
        "sequence": number,
        "payload": payload or {},
    }


def _append(path, *events):
    with path.open("a", encoding="utf-8") as event_file:
        for event in events:
            serialized = json.dumps(event, separators=(",", ":"))
            event_file.write(serialized + "\n")


def _count(store, table):
    return store.connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]


def test_ingestion_is_idempotent_and_resumes_from_committed_offset(tmp_path):
    events_path = tmp_path / "events.jsonl"
    _append(events_path, _event(0, "run.started", {"experiment_id": "exp-a"}))
    store = EventStore(tmp_path / "pithos.db")

    first = store.ingest(events_path)
    duplicate = store.ingest(events_path)
    _append(events_path, _event(1, "tool.finished", {"tool_name": "read"}))
    resumed = store.ingest(events_path)

    assert first["ingested"] == 1
    assert duplicate["ingested"] == 0
    assert resumed["ingested"] == 1
    assert _count(store, "events") == 2
    assert _count(store, "tool_calls") == 1
    store.close()


def test_invalid_line_is_quarantined_without_blocking_following_event(tmp_path):
    events_path = tmp_path / "events.jsonl"
    events_path.write_text("not-json\n", encoding="utf-8")
    _append(events_path, _event(0, "command.finished", {"exit_code": 0}))
    store = EventStore(tmp_path / "pithos.db")

    result = store.ingest(events_path)

    assert result["ingested"] == 1
    assert result["quarantined"] == 1
    assert _count(store, "commands") == 1
    assert _count(store, "quarantine") == 1
    store.close()


def test_truncated_source_is_rejected(tmp_path):
    events_path = tmp_path / "events.jsonl"
    _append(events_path, _event(0, "run.started"))
    store = EventStore(tmp_path / "pithos.db")
    store.ingest(events_path)
    events_path.write_text("", encoding="utf-8")

    with pytest.raises(IngestionError, match="truncated"):
        store.ingest(events_path)

    store.close()


def test_partial_final_line_is_left_for_the_next_ingestion(tmp_path):
    events_path = tmp_path / "events.jsonl"
    serialized = json.dumps(_event(0, "run.started"))
    events_path.write_text(serialized[:-5], encoding="utf-8")
    store = EventStore(tmp_path / "pithos.db")

    partial = store.ingest(events_path)
    with events_path.open("a", encoding="utf-8") as event_file:
        event_file.write(serialized[-5:] + "\n")
    complete = store.ingest(events_path)

    assert partial["offset_bytes"] == 0
    assert partial["quarantined"] == 0
    assert complete["ingested"] == 1
    store.close()


def test_run_session_pr_and_full_model_content_remain_queryable(tmp_path):
    events_path = tmp_path / "events.jsonl"
    _append(
        events_path,
        _event(
            0,
            "run.started",
            {"experiment_id": "exp-a", "micro_rush_id": "rush-a", "model": "qwen"},
        ),
        _event(1, "model.response", {"role": "assistant", "content": "full response"}),
        _event(2, "git.pr_create", {"url": "https://github.com/acme/repo/pull/7"}),
        _event(
            3,
            "run.finished",
            {
                "status": "completed",
                "session_id": "session-a",
                "duration_ms": 1200,
                "input_tokens": 10,
                "output_tokens": 5,
                "total_tokens": 15,
                "tool_calls": 2,
                "tool_failures": 1,
            },
        ),
    )
    store = EventStore(tmp_path / "pithos.db")

    store.ingest(events_path)

    run = store.connection.execute("SELECT * FROM runs WHERE run_id = ?", (RUN_ID,)).fetchone()
    message = store.connection.execute("SELECT * FROM model_messages").fetchone()
    assert run["micro_rush_id"] == "rush-a"
    assert run["session_id"] == "session-a"
    assert run["pull_request_url"].endswith("/pull/7")
    assert run["duration_ms"] == 1200
    assert run["total_tokens"] == 15
    assert run["tool_failures"] == 1
    assert message["content"] == "full response"
    assert "full response" in message["payload_json"]
    store.close()


@pytest.mark.parametrize(
    ("event_type", "table"),
    [
        ("file.changed", "file_changes"),
        ("test.finished", "tests"),
        ("dependency.installed", "dependencies"),
        ("network.requested", "network_events"),
        ("harness.promoted", "harness_events"),
        ("telegram.sent", "telegram_events"),
    ],
)
def test_domain_events_have_a_queryable_projection(tmp_path, event_type, table):
    events_path = tmp_path / f"{table}.jsonl"
    _append(events_path, _event(0, event_type, {"detail": table}))
    store = EventStore(tmp_path / f"{table}.db")

    store.ingest(events_path)

    assert _count(store, table) == 1
    store.close()


def test_second_migration_preserves_existing_raw_events(tmp_path):
    database = tmp_path / "legacy.db"
    connection = sqlite3.connect(database)
    connection.execute(
        "CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    connection.executescript(MIGRATIONS[0])
    connection.execute("INSERT INTO schema_migrations VALUES (1, datetime('now'))")
    connection.execute(
        """
        INSERT INTO events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "evt-20260823T120000.000000Z-a1b2c3",
            RUN_ID,
            "2026-08-23T12:00:00+00:00",
            "model.response",
            "test",
            0,
            '{"content":"preserved"}',
            '{"raw":"preserved"}',
            "/tmp/events.jsonl",
            1,
        ),
    )
    connection.commit()
    connection.close()

    store = EventStore(database)

    raw = store.connection.execute("SELECT raw_json FROM events").fetchone()[0]
    versions = store.connection.execute("SELECT version FROM schema_migrations").fetchall()
    assert raw == '{"raw":"preserved"}'
    assert [row[0] for row in versions] == [1, 2, 3]
    assert store.connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    store.close()


def test_squid_access_log_is_attributed_and_projected_incrementally(tmp_path):
    access_log = tmp_path / "access.log"
    access_log.write_text(
        f"1787486400.123 {RUN_ID} 172.18.0.2 GET https://pypi.org/simple 200 321\n"
        "1787486401.000 - 172.18.0.2 GET https://forbidden.example 403 0\n"
    )
    store = EventStore(tmp_path / "pithos.db")

    first = store.ingest_squid(access_log)
    second = store.ingest_squid(access_log)

    network = store.connection.execute("SELECT payload_json FROM network_events").fetchone()
    assert first["ingested"] == 1
    assert first["quarantined"] == 1
    assert second["ingested"] == 0
    assert json.loads(network[0])["url"] == "https://pypi.org/simple"
    store.close()


def test_squid_line_without_proxy_username_uses_the_single_active_run(tmp_path):
    access_log = tmp_path / "access.log"
    access_log.write_text("1787486400.123 - 172.18.0.2 CONNECT github.com:443 200 12\n")
    store = EventStore(tmp_path / "pithos.db")
    store.connection.execute(
        """
        INSERT INTO runs(run_id, status, started_at)
        VALUES (?, 'running', '2026-08-23T11:00:00+00:00')
        """,
        (RUN_ID,),
    )
    store.connection.commit()

    result = store.ingest_squid(access_log)

    assert result["ingested"] == 1
    event = store.connection.execute("SELECT run_id FROM network_events").fetchone()
    assert event["run_id"] == RUN_ID
    store.close()
