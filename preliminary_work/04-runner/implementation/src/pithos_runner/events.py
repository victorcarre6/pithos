"""Write valid append-only Pithos events for one run."""

import fcntl
import json
import os
import secrets
from datetime import UTC, datetime
from pathlib import Path

from pithos_live_log import LiveLog


class EventWriter:
    """Append one flushed JSON event per line with a monotone sequence."""

    def __init__(self, path: Path, run_id: str, source: str = "runner") -> None:

        self.path = path
        self.run_id = run_id
        self.source = source
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock_path = self.path.with_suffix(".lock")

    def append(self, event_type: str, payload: dict) -> dict:
        now = datetime.now(UTC)
        timestamp_token = now.strftime("%Y%m%dT%H%M%S.%fZ")
        with self.lock_path.open("a", encoding="utf-8") as lock_file:
            fcntl.flock(lock_file, fcntl.LOCK_EX)
            sequence = self._next_sequence()
            event = {
                "schema_version": "1.0",
                "event_id": f"evt-{timestamp_token}-{secrets.token_hex(3)}",
                "run_id": self.run_id,
                "timestamp": now.isoformat(),
                "type": event_type,
                "source": self.source,
                "sequence": sequence,
                "payload": payload,
            }
            serialized = json.dumps(event, separators=(",", ":"))

            with self.path.open("a", encoding="utf-8") as event_file:
                event_file.write(serialized + "\n")
                event_file.flush()
                os.fsync(event_file.fileno())
            fcntl.flock(lock_file, fcntl.LOCK_UN)

        if len(self.path.parents) >= 3 and self.path.parent.parent.name in {"runs", "missions"}:
            logs_root = self.path.parents[2]
            level = _live_level(event_type, payload)
            try:
                LiveLog(logs_root).write(self.run_id, level, self.source, event_type)
            except OSError:
                pass

        return event

    def _next_sequence(self) -> int:
        if not self.path.exists():
            return 0

        with self.path.open(encoding="utf-8") as event_file:
            event_count = sum(1 for line in event_file if line.strip())

        return event_count


def _live_level(event_type: str, payload: dict) -> str:
    if event_type == "run.finished" and payload.get("status") not in {"completed", "running"}:
        return "ERROR"
    if event_type.endswith(".failed") or payload.get("is_error"):
        return "ERROR"

    return "INFO"
