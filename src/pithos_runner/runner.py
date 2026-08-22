"""Orchestrate one isolated Pi run and persist its authoritative outcome."""

import json
import os
import secrets
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pithos_capability_probe.runner import classify_protocol, parse_events
from pithos_continuity import publish_report

from .events import EventWriter
from .lock import RunLock
from .process import run_monitored
from .state import read_state, write_state


LOOP_WARNING = "[WARNING] Boucle récursive infinie détectée."


@dataclass(frozen=True)
class RunnerConfiguration:
    """Paths and bounded policies for one experiment runner."""

    experiment_id: str
    workspace: Path
    logs_root: Path
    pi_config_dir: Path
    pi_executable: str = "pi"
    provider: str = "ollama"
    model: str = "qwen3.8:27b"
    timeout_seconds: int = 3600
    repeat_limit: int = 5
    heartbeat_seconds: float = 30


def new_run_id() -> str:
    now = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    return f"run-{now}-{secrets.token_hex(3)}"


def _write_run(path: Path, content: dict) -> None:
    temporary_path = path.with_suffix(".tmp")
    temporary_path.write_text(json.dumps(content, indent=2) + "\n", encoding="utf-8")
    temporary_path.replace(path)


def run_once(configuration: RunnerConfiguration) -> dict:
    """Execute one fresh Pi session unless the persistent runner state is paused."""

    runtime_dir = configuration.logs_root / "runtime"
    state_path = runtime_dir / "state.json"
    state = read_state(state_path)
    if state["paused"]:
        raise RuntimeError(f"runner is paused: {state['reason']}")

    lock = RunLock(runtime_dir / "runner.lock")
    with lock:
        run_id = new_run_id()
        run_dir = configuration.logs_root / "runs" / run_id
        run_dir.mkdir(parents=True)
        events = EventWriter(run_dir / "events.jsonl", run_id)
        started_at = datetime.now(UTC).isoformat()
        run_document = {
            "schema_version": "1.0",
            "run_id": run_id,
            "experiment_id": configuration.experiment_id,
            "micro_rush_id": None,
            "status": "running",
            "started_at": started_at,
            "finished_at": None,
            "branch": None,
            "commit_before": None,
            "commit_after": None,
            "artifacts_dir": f"runs/{run_id}",
            "stop_reason": None,
            "success": {"process": None, "protocol": None, "task": None, "report": None},
        }
        _write_run(run_dir / "run.json", run_document)
        events.append("run.started", {"model": configuration.model})

        latest_path = configuration.logs_root / "latest.md"
        continuity_dir = configuration.workspace / ".pithos"
        continuity_dir.mkdir(exist_ok=True)
        if latest_path.exists():
            shutil.copy2(latest_path, continuity_dir / "LATEST.md")

        report_path = continuity_dir / "report.md"
        report_path.unlink(missing_ok=True)
        session_dir = run_dir / "sessions"
        session_dir.mkdir()
        command = [
            configuration.pi_executable,
            "--approve",
            "--provider",
            configuration.provider,
            "--model",
            configuration.model,
            "--thinking",
            "off",
            "--mode",
            "json",
            "--print",
            "--session-dir",
            str(session_dir),
            (
                "Read .pithos/LATEST.md if it exists, continue one micro-rush, then write the validated "
                "continuity report to .pithos/report.md before finishing."
            ),
        ]
        environment = os.environ.copy()
        environment["PI_CODING_AGENT_DIR"] = str(configuration.pi_config_dir)
        environment["PITHOS_RUN_ID"] = run_id
        outcome = run_monitored(
            command,
            cwd=configuration.workspace,
            environment=environment,
            stdout_path=run_dir / "stdout.jsonl",
            stderr_path=run_dir / "stderr.log",
            timeout_seconds=configuration.timeout_seconds,
            repeat_limit=configuration.repeat_limit,
            heartbeat_seconds=configuration.heartbeat_seconds,
            on_heartbeat=lambda: events.append("run.heartbeat", {}),
        )

        stdout = (run_dir / "stdout.jsonl").read_text(encoding="utf-8")
        pi_events, parse_errors = parse_events(stdout)
        protocol_success, _ = classify_protocol(pi_events, parse_errors)

        report_success = False
        if report_path.exists():
            try:
                publish_report(report_path, configuration.logs_root)
                report_success = True
            except (OSError, ValueError):
                report_success = False

        if outcome.loop_detected:
            status = "paused"
            stop_reason = LOOP_WARNING
            write_state(state_path, True, stop_reason)
        elif outcome.timed_out:
            status = "timed_out"
            stop_reason = "run exceeded its configured timeout"
        elif outcome.exit_code == 0 and report_success:
            status = "completed"
            stop_reason = None
        else:
            status = "failed"
            stop_reason = "Pi failed or did not publish a valid report"

        run_document["status"] = status
        run_document["finished_at"] = datetime.now(UTC).isoformat()
        run_document["stop_reason"] = stop_reason
        run_document["success"] = {
            "process": outcome.exit_code == 0,
            "protocol": protocol_success,
            "task": None,
            "report": report_success,
        }
        _write_run(run_dir / "run.json", run_document)
        events.append("run.finished", {"status": status, "stop_reason": stop_reason})

        return run_document
