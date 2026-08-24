"""Launch one bounded multi-session mission through host-side brokers."""

import json
import secrets
from datetime import datetime, timezone
from pathlib import Path

from pithos_runner.events import EventWriter
from pithos_runner.runner import RunnerConfiguration

from .campaign import CommandValidator, ContextFactory, LocalFinalizer
from .client import send_request
from .controller import Orchestrator
from .pi_phase import PiPhaseRunner
from .state import MissionState, StateStore


def launch(workspace, logs_root, git_socket=None, telegram_socket=None):
    """Execute one orchestrated mission for a generated experiment."""

    workspace = Path(workspace).resolve()
    logs_root = Path(logs_root).expanduser().resolve()
    project = json.loads((workspace / ".pithos.json").read_text(encoding="utf-8"))
    validation_command = project.get("validation_command")
    if not isinstance(validation_command, list) or not validation_command:
        raise ValueError(".pithos.json requires a non-empty validation_command list")

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
    state = MissionState(mission_id, project["experiment_id"])
    _notify(telegram_socket, state, "started")

    try:
        context_factory = ContextFactory(workspace, target_paths=project.get("target_files"))
        result = orchestrator.run(state, context_factory)
    except KeyboardInterrupt:
        orchestrator.interrupt(state, "operator interrupt")
        _notify(telegram_socket, state, "finished")
        raise
    _notify(telegram_socket, result, "finished")

    return result


def _notify(socket_path, state, event):
    """Send one best-effort lifecycle notification outside the model."""

    if not socket_path:
        return

    completed = state.status == "completed"
    kind = "INFO" if event == "started" or completed else "WARNING"
    text = f"Pithos mission {state.mission_id} {event}: {state.status}."
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
