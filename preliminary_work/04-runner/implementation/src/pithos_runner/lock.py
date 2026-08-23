"""Atomic single-run lock that never signals an unrelated process."""

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


class LockHeld(RuntimeError):
    """Indicate that another live process owns the runner lock."""


def _pid_is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True

    return True


@dataclass
class RunLock:
    """Hold a lock directory for the lifetime of one runner invocation."""

    path: Path

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

        try:
            self.path.mkdir()
        except FileExistsError:
            self._recover_stale_lock()
            self.path.mkdir()

        metadata = {
            "pid": os.getpid(),
            "created_at": datetime.now(UTC).isoformat(),
        }
        (self.path / "owner.json").write_text(json.dumps(metadata) + "\n", encoding="utf-8")

    def _recover_stale_lock(self) -> None:
        owner_path = self.path / "owner.json"
        try:
            metadata = json.loads(owner_path.read_text(encoding="utf-8"))
            pid = int(metadata["pid"])
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
            raise LockHeld(f"lock metadata is unreadable: {owner_path}") from error

        if _pid_is_alive(pid):
            raise LockHeld(f"runner lock is held by live PID {pid}")

        owner_path.unlink(missing_ok=True)
        try:
            self.path.rmdir()
        except OSError as error:
            raise LockHeld(f"stale lock contains unexpected files: {self.path}") from error

    def release(self) -> None:
        owner_path = self.path / "owner.json"
        owner_path.unlink(missing_ok=True)
        try:
            self.path.rmdir()
        except FileNotFoundError:
            pass

    def __enter__(self):
        self.acquire()

        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.release()

