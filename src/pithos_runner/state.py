"""Persist the runner pause state across scheduled wake-ups."""

import json
from datetime import UTC, datetime
from pathlib import Path


def read_state(path: Path) -> dict:
    if not path.exists():
        return {"paused": False, "reason": None, "updated_at": None}

    return json.loads(path.read_text(encoding="utf-8"))


def write_state(path: Path, paused: bool, reason: str | None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    state = {
        "paused": paused,
        "reason": reason,
        "updated_at": datetime.now(UTC).isoformat(),
    }
    temporary_path = path.with_suffix(".tmp")
    temporary_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    temporary_path.replace(path)

