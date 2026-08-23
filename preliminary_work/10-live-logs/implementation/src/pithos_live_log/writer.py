"""Serialize, flush and rotate the global Pithos live log."""

import fcntl
import os
from datetime import UTC, datetime
from pathlib import Path


LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "EMERGENCY"}


class LiveLog:
    """Append one human-readable line under an inter-process lock."""

    def __init__(self, logs_root: Path, rotate_bytes: int = 10 * 1024 * 1024) -> None:
        self.path = logs_root / "live.log"
        self.lock_path = logs_root / "runtime" / "live.lock"
        self.archive_dir = logs_root / "archive" / "live"
        self.rotate_bytes = rotate_bytes

    def write(self, run_id: str, level: str, component: str, message: str) -> str:
        if level not in LEVELS:
            raise ValueError(f"unsupported live log level: {level}")
        if "\n" in run_id or "\n" in component:
            raise ValueError("run id and component must fit on one line")

        timestamp = datetime.now(UTC).isoformat(timespec="milliseconds")
        single_line = message.replace("\r", "\\r").replace("\n", "\\n")
        content = f"{timestamp} [{level}] [{run_id}] [{component}] {single_line}\n"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)

        with self.lock_path.open("a", encoding="utf-8") as lock_file:
            fcntl.flock(lock_file, fcntl.LOCK_EX)
            self._rotate_if_needed(len(content.encode("utf-8")))
            with self.path.open("a", encoding="utf-8") as live_file:
                live_file.write(content)
                live_file.flush()
                os.fsync(live_file.fileno())
            fcntl.flock(lock_file, fcntl.LOCK_UN)

        return content.rstrip("\n")

    def _rotate_if_needed(self, incoming_bytes: int) -> None:
        current_bytes = self.path.stat().st_size if self.path.exists() else 0
        if current_bytes == 0 or current_bytes + incoming_bytes <= self.rotate_bytes:
            return

        self.archive_dir.mkdir(parents=True, exist_ok=True)
        token = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
        archive_path = self.archive_dir / f"live-{token}.log"
        self.path.replace(archive_path)
