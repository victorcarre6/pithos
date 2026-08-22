"""Write valid append-only Pithos events for one run."""

import json
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
        self.sequence = 0
        if self.path.exists():
            with self.path.open(encoding="utf-8") as event_file:
                self.sequence = sum(1 for line in event_file if line.strip())

    def append(self, event_type: str, payload: dict) -> dict:
        now = datetime.now(UTC)
        timestamp_token = now.strftime("%Y%m%dT%H%M%S.%fZ")
        event = {
            "schema_version": "1.0",
            "event_id": f"evt-{timestamp_token}-{secrets.token_hex(3)}",
            "run_id": self.run_id,
            "timestamp": now.isoformat(),
            "type": event_type,
            "source": self.source,
            "sequence": self.sequence,
            "payload": payload,
        }
        serialized = json.dumps(event, separators=(",", ":"))

        with self.path.open("a", encoding="utf-8") as event_file:
            event_file.write(serialized + "\n")
            event_file.flush()

        if len(self.path.parents) >= 3 and self.path.parent.parent.name == "runs":
            logs_root = self.path.parents[2]
            level = _live_level(event_type, payload)
            LiveLog(logs_root).write(self.run_id, level, self.source, event_type)

        self.sequence += 1

        return event


def _live_level(event_type: str, payload: dict) -> str:
    if event_type == "run.finished" and payload.get("status") not in {"completed", "running"}:
        return "ERROR"
    if event_type.endswith(".failed") or payload.get("is_error"):
        return "ERROR"

    return "INFO"
