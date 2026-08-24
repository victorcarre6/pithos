"""Atomic mission state for resumable multi-session work."""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path


PHASES = {"preflight", "implement", "test", "repair", "review", "finalize", "done", "failed", "interrupted"}


def now():
    """Return one timezone-aware timestamp."""

    return datetime.now(timezone.utc).isoformat()


@dataclass
class MissionState:
    """Persist only facts required to resume a mission."""

    mission_id: str
    experiment_id: str
    phase: str = "preflight"
    status: str = "running"
    repair_attempts: int = 0
    max_repairs: int = 3
    failure_summary: str = ""
    changed_files: list = field(default_factory=list)
    evidence: list = field(default_factory=list)
    history: list = field(default_factory=list)
    artifacts: dict = field(default_factory=dict)
    updated_at: str = field(default_factory=now)


class StateStore:
    """Read and atomically replace one mission state document."""

    def __init__(self, path):
        self.path = Path(path)

    def save(self, state):
        if state.phase not in PHASES:
            raise ValueError(f"unsupported mission phase: {state.phase}")

        state.updated_at = now()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(asdict(state), indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.path)

    def load(self):
        payload = json.loads(self.path.read_text(encoding="utf-8"))

        return MissionState(**payload)
