"""Launch one bounded multi-session mission through host-side brokers."""

import json
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path

from pithos_runner.events import EventWriter
from pithos_runner.runner import RunnerConfiguration

from .campaign import CommandValidator, ContextFactory, LocalFinalizer
from .client import send_request
from .controller import Orchestrator
from .pi_phase import PiPhaseRunner
from .recap import generate_recap
from .state import MissionState, StateStore


def launch(workspace, logs_root, git_socket=None, telegram_socket=None):
    """Execute one orchestrated mission for a generated experiment."""

    workspace = Path(workspace).resolve()
    logs_root = Path(logs_root).expanduser().resolve()
    project = json.loads((workspace / ".pithos.json").read_text(encoding="utf-8"))
    micro_rush_id = project.get("micro_rush_id", project["experiment_id"])
    validation_command = project.get("validation_command")
    if not isinstance(validation_command, list) or not validation_command:
        raise ValueError(".pithos.json requires a non-empty validation_command list")
    for field in ("title", "description"):
        if not isinstance(project.get(field), str) or not project[field].strip():
            raise ValueError(f".pithos.json requires a non-empty {field}")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    mission_id = f"run-{timestamp}-{secrets.token_hex(3)}"
    mission_root = logs_root / "missions" / mission_id
    state_store = StateStore(mission_root / "state.json")
    events = EventWriter(mission_root / "events.jsonl", mission_id)
    configuration = RunnerConfiguration(
        experiment_id=project["experiment_id"],
        workspace=workspace,
        logs_root=logs_root,
        pi_config_dir=Path(project["pi_config"]).resolve(),
        runtime=project.get("runtime", "host"),
        model=project.get("model", "maternion/ling-3.0-tiny:8b"),
        timeout_seconds=300,
        repeat_limit=3,
    )
    phase_runner = PiPhaseRunner(configuration, mission_root, events)
    validator = CommandValidator(workspace, validation_command)
    git_send = None
    if git_socket:
        git_send = lambda request: send_request(git_socket, request)
    finalizer = LocalFinalizer(workspace, mission_root, logs_root, git_send)
    orchestrator = Orchestrator(state_store, phase_runner, validator, finalizer)
    state = MissionState(mission_id, project["experiment_id"], micro_rush_id=micro_rush_id)
    started_monotonic = time.monotonic()
    events.append(
        "run.started",
        {
            "experiment_id": state.experiment_id,
            "micro_rush_id": f"rush-{state.micro_rush_id}",
            "model": configuration.model,
        },
    )
    _notify(telegram_socket, project, state, "started")

    try:
        context_factory = ContextFactory(workspace, target_paths=project.get("target_files"))
        result = orchestrator.run(state, context_factory)
    except KeyboardInterrupt:
        orchestrator.interrupt(state, "operator interrupt")
        finish_payload = _finish_payload(state, mission_root, started_monotonic)
        events.append("run.finished", finish_payload)
        _notify(telegram_socket, project, state, "finished", finish_payload)
        raise
    finish_payload = _finish_payload(result, mission_root, started_monotonic)
    events.append("run.finished", finish_payload)
    _notify(telegram_socket, project, result, "finished", finish_payload)
    _send_recap(
        telegram_socket,
        project,
        result,
        finish_payload,
        configuration.model,
        mission_root,
        events,
    )

    return result


def _finish_payload(state, mission_root, started_monotonic):
    """Aggregate phase metrics for the terminal run event."""

    # métriques de toutes les sessions bornées
    metrics = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "tool_calls": 0,
        "tool_failures": 0,
    }
    for path in sorted((Path(mission_root) / "phases").glob("*/result.json")):
        result = json.loads(path.read_text(encoding="utf-8"))
        phase_metrics = result.get("metrics") or {}
        for name in metrics:
            metrics[name] += int(phase_metrics.get(name) or 0)

    # état terminal + durée murale
    payload = {
        "status": state.status,
        "stop_reason": state.failure_summary or None,
        "duration_ms": round((time.monotonic() - started_monotonic) * 1000),
        **metrics,
    }

    return payload


def _notify(socket_path, project, state, event, finish_payload=None):
    """Send one best-effort lifecycle notification outside the model."""

    if not socket_path:
        return

    completed = state.status == "completed"
    kind = "INFO" if event == "started" or completed else "WARNING"
    text = _lifecycle_text(project, state, event, finish_payload)
    request = {
        "request_id": f"{state.mission_id}-orchestrated-{event}",
        "run_id": state.mission_id,
        "kind": kind,
        "text": text,
    }
    try:
        send_request(socket_path, request)
    except (OSError, RuntimeError, ValueError):
        pass


def _lifecycle_text(project, state, event, finish_payload=None):
    """Build one authoritative, human-readable lifecycle message."""

    title = project["title"].strip()
    description = project["description"].strip()
    if event == "started":
        return f"🚀 {title}\n\n{description}\nMission {state.mission_id} démarrée."

    payload = finish_payload or {}
    duration_seconds = _duration_seconds(payload)
    conclusion = "Validation réussie" if state.status == "completed" else "Mission non terminée"
    details = f"{conclusion} en {duration_seconds} s après {state.repair_attempts} réparation(s)."
    if state.status != "completed" and state.failure_summary:
        reason = state.failure_summary.splitlines()[0][:240]
        details = f"{details}\nCause : {reason}"
    pull_request = state.artifacts.get("pull_request")
    if pull_request:
        details = f"{details}\nPR : {pull_request}"

    return f"{'✅' if state.status == 'completed' else '⚠️'} {title}\n\n{description}\n{details}"


def _send_recap(socket_path, project, state, finish_payload, model, mission_root, events):
    """Generate and send one best-effort human recap after terminal evidence."""

    if not socket_path:
        return

    # faits autoritaires seulement
    facts = {
        "title": project["title"].strip(),
        "goal": project["description"].strip(),
        "status": state.status,
        "changed_files": state.changed_files,
        "repairs": state.repair_attempts,
        "validation": "PASS" if state.status == "completed" else "FAIL",
        "duration_seconds": _duration_seconds(finish_payload),
        "tool_calls": int(finish_payload.get("tool_calls", 0)),
        "tool_failures": int(finish_payload.get("tool_failures", 0)),
        "pull_request": state.artifacts.get("pull_request"),
        "stop_reason": state.failure_summary or None,
    }
    artifact_path = Path(mission_root) / "telegram-recap.txt"
    try:
        text = generate_recap(model, facts, artifact_path)
    except (OSError, RuntimeError, ValueError):
        events.append("telegram.recap_failed", {"model": model})

        return

    events.append(
        "telegram.recap_generated",
        {
            "model": model,
            "characters": len(text),
            "artifact": str(artifact_path),
        },
    )
    request = {
        "request_id": f"{state.mission_id}-orchestrated-recap",
        "run_id": state.mission_id,
        "kind": "INFO" if state.status == "completed" else "WARNING",
        "text": text,
    }
    try:
        send_request(socket_path, request)
    except (OSError, RuntimeError, ValueError):
        pass


def _duration_seconds(payload):
    """Round a millisecond duration to the nearest displayed second."""

    return (int(payload.get("duration_ms", 0)) + 500) // 1000
