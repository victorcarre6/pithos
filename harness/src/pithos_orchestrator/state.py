"""Atomic mission state for resumable multi-session work."""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path


PHASES = {
    "plan_todo",
    "author_oracle",
    "preflight",
    "implement",
    "test",
    "repair",
    "review",
    "propose_next_rush",
    "finalize",
    "done",
    "failed",
    "interrupted",
}


def now():
    """Return one timezone-aware timestamp."""

    return datetime.now(timezone.utc).isoformat()


@dataclass
class MissionState:
    """Persist only facts required to resume a mission."""

    mission_id: str
    experiment_id: str
    micro_rush_id: str = ""
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
    todo: list = field(default_factory=list)
    todo_index: int = 0


def current_item(project, state):
    """Return the active todo item's title/description/target_files, or the rush-level fields.

    A mission without a plan (`state.todo` empty -- no planner configured, or planning fell back)
    behaves exactly as if it had a single implicit item covering the whole rush.
    """

    if state.todo:
        return state.todo[state.todo_index]

    return {
        "title": project.get("title", ""),
        "description": project.get("description", ""),
        "target_files": project.get("target_files"),
    }


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
