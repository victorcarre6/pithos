"""Archive validated reports and atomically publish the global latest report."""

import os
from pathlib import Path

from pithos_contracts import validate_report


class ContinuityError(RuntimeError):
    """Report an unsafe or inconsistent continuity publication."""


def _write_atomic(path: Path, content: bytes) -> None:
    temporary_path = path.parent / f".{path.name}.{os.getpid()}.tmp"

    try:
        with temporary_path.open("wb") as temporary_file:
            temporary_file.write(content)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        temporary_path.replace(path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def publish_report(report_path: Path, logs_root: Path) -> Path:
    """Validate, archive and publish one report without overwriting run history."""

    metadata = validate_report(report_path)
    run_id = metadata["run_id"]
    content = report_path.read_bytes()

    run_directory = logs_root / "runs" / run_id
    run_directory.mkdir(parents=True, exist_ok=True)
    archive_path = run_directory / "report.md"

    if archive_path.exists() and archive_path.read_bytes() != content:
        raise ContinuityError(f"archive already exists with different content: {archive_path}")
    if not archive_path.exists():
        _write_atomic(archive_path, content)

    latest_path = logs_root / "latest.md"
    latest_path.parent.mkdir(parents=True, exist_ok=True)
    _write_atomic(latest_path, content)

    return archive_path


def load_latest_report(logs_root: Path) -> tuple[dict, str]:
    """Load and validate the single global report used by a new session."""

    latest_path = logs_root / "latest.md"
    if not latest_path.exists():
        raise ContinuityError(f"latest report is absent: {latest_path}")

    metadata = validate_report(latest_path)
    content = latest_path.read_text(encoding="utf-8")

    return metadata, content

