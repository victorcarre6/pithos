"""Write valid append-only Pithos events for one run."""

import json
import secrets
from datetime import UTC, datetime
from pathlib import Path


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

        self.sequence += 1

        return event
