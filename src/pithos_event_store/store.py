"""Incrementally ingest JSONL while quarantining invalid lines."""

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from pithos_contracts import ValidationFailure, validate_document

from .migrations import migrate


class IngestionError(RuntimeError):
    """Report mutation of an append-only source or a database failure."""


DOMAIN_TABLES = {
    "tool": "tool_calls",
    "command": "commands",
    "file": "file_changes",
    "test": "tests",
    "dependency": "dependencies",
    "network": "network_events",
    "harness": "harness_events",
    "git": "git_events",
    "telegram": "telegram_events",
    "model": "model_messages",
}


class EventStore:
    """Maintain a WAL SQLite projection and a cursor for each JSONL source."""

    def __init__(self, database_path: Path) -> None:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(database_path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA foreign_keys=ON")
        migrate(self.connection)

    def close(self) -> None:
        self.connection.close()

    def ingest(self, path: Path) -> dict:
        """Resume one event file from its committed byte offset."""

        resolved_path = str(path.resolve())
        source = self.connection.execute(
            "SELECT offset_bytes, line_number FROM ingestion_sources WHERE file_path = ?",
            (resolved_path,),
        ).fetchone()
        offset = source["offset_bytes"] if source else 0
        line_number = source["line_number"] if source else 0
        size = path.stat().st_size
        if size < offset:
            raise IngestionError(f"append-only source was truncated: {path}")

        ingested = 0
        quarantined = 0
        with path.open("rb") as event_file, self.connection:
            event_file.seek(offset)
            while raw_line := event_file.readline():
                line_number += 1
                raw_content = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
                if not raw_content.strip():
                    continue
                try:
                    event = json.loads(raw_content)
                    validate_document(event, "event")
                except (json.JSONDecodeError, ValidationFailure) as error:
                    self._quarantine(resolved_path, line_number, raw_content, str(error))
                    quarantined += 1
                    continue

                inserted = self._insert_event(event, raw_content, resolved_path, line_number)
                if inserted:
                    self._project(event)
                    ingested += 1

            final_offset = event_file.tell()
            self.connection.execute(
                """
                INSERT INTO ingestion_sources(file_path, offset_bytes, line_number, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(file_path) DO UPDATE SET
                    offset_bytes = excluded.offset_bytes,
                    line_number = excluded.line_number,
                    updated_at = excluded.updated_at
                """,
                (resolved_path, final_offset, line_number, datetime.now(UTC).isoformat()),
            )

        return {
            "path": resolved_path,
            "ingested": ingested,
            "quarantined": quarantined,
            "offset_bytes": final_offset,
            "line_number": line_number,
        }

    def _insert_event(self, event: dict, raw_content: str, file_path: str, line_number: int) -> bool:
        cursor = self.connection.execute(
            """
            INSERT OR IGNORE INTO events(
                event_id, run_id, timestamp, type, source, sequence, payload_json,
                raw_json, file_path, line_number
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event["event_id"],
                event["run_id"],
                event["timestamp"],
                event["type"],
                event["source"],
                event.get("sequence"),
                json.dumps(event["payload"], separators=(",", ":")),
                raw_content,
                file_path,
                line_number,
            ),
        )

        return cursor.rowcount == 1

    def _quarantine(self, file_path: str, line_number: int, raw_content: str, error: str) -> None:
        self.connection.execute(
            """
            INSERT OR IGNORE INTO quarantine(file_path, line_number, raw_content, error, quarantined_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (file_path, line_number, raw_content, error, datetime.now(UTC).isoformat()),
        )

    def _project(self, event: dict) -> None:
        domain, action = event["type"].split(".", 1)
        payload = event["payload"]
        payload_json = json.dumps(payload, separators=(",", ":"))

        if domain == "run":
            self._project_run(event, action)
            return
        table = DOMAIN_TABLES.get(domain)
        if not table:
            return
        if table == "tool_calls":
            self.connection.execute(
                """
                INSERT INTO tool_calls(event_id, run_id, action, tool_name, tool_call_id, is_error, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event["event_id"], event["run_id"], action, payload.get("tool_name"),
                    payload.get("tool_call_id"), payload.get("is_error"), payload_json,
                ),
            )
        elif table == "model_messages":
            self.connection.execute(
                """
                INSERT INTO model_messages(event_id, run_id, action, role, content, payload_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event["event_id"], event["run_id"], action, payload.get("role"),
                    payload.get("content"), payload_json,
                ),
            )
        else:
            self.connection.execute(
                f"INSERT INTO {table}(event_id, run_id, action, payload_json) VALUES (?, ?, ?, ?)",
                (event["event_id"], event["run_id"], action, payload_json),
            )

        if domain == "git" and action in {"pr_create", "pr_view"}:
            pull_request = payload.get("pull_request") or {}
            url = payload.get("url") or pull_request.get("url")
            if url:
                self.connection.execute(
                    "UPDATE runs SET pull_request_url = ? WHERE run_id = ?",
                    (url, event["run_id"]),
                )

    def _project_run(self, event: dict, action: str) -> None:
        payload = event["payload"]
        if action == "started":
            self.connection.execute(
                """
                INSERT INTO runs(run_id, experiment_id, micro_rush_id, model, status, started_at)
                VALUES (?, ?, ?, ?, 'running', ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    experiment_id = excluded.experiment_id,
                    micro_rush_id = excluded.micro_rush_id,
                    model = excluded.model,
                    status = excluded.status,
                    started_at = excluded.started_at
                """,
                (
                    event["run_id"], payload.get("experiment_id"), payload.get("micro_rush_id"),
                    payload.get("model"), event["timestamp"],
                ),
            )
        elif action == "finished":
            self.connection.execute(
                """
                INSERT INTO runs(run_id, session_id, status, finished_at, stop_reason)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    session_id = excluded.session_id,
                    status = excluded.status,
                    finished_at = excluded.finished_at,
                    stop_reason = excluded.stop_reason
                """,
                (
                    event["run_id"], payload.get("session_id"), payload.get("status"),
                    event["timestamp"], payload.get("stop_reason"),
                ),
            )

