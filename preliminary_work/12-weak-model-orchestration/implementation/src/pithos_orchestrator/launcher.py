"""Launch one bounded multi-session mission through host-side brokers."""

import json
import re
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path

from pithos_runner.events import EventWriter
from pithos_runner.runner import RunnerConfiguration

from .campaign import CommandValidator, ContextFactory, LocalFinalizer
from .client import send_request
from .controller import Orchestrator
from .next_rush import NextRushAuthor
from .oracle import OracleAuthor
from .pi_phase import PiPhaseRunner
from .plan_todo import MAX_ITEMS, TodoPlanner
from .recap import generate_recap
from .state import MissionState, StateStore


# worst case per todo item: plan_todo(1) + author_oracle(1) + preflight(1) + implement(1) +
# (test+repair) * max_repairs(3) + test(1), times up to MAX_ITEMS, plus propose_next_rush + finalize
_MAX_ORCHESTRATOR_STEPS = 1 + MAX_ITEMS * 12 + 2


# same identifier shape the report-metadata and micro-rush contracts require (contracts/v1/*.schema.json);
# checked here too so a bad id fails before a Docker/Pi session runs, not only at finalize
_IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


def launch(workspace, logs_root, git_socket=None, telegram_socket=None):
    """Execute one orchestrated mission for a generated experiment."""

    workspace = Path(workspace).resolve()
    logs_root = Path(logs_root).expanduser().resolve()
    project = json.loads((workspace / ".pithos.json").read_text(encoding="utf-8"))
    experiment_id = project["experiment_id"]
    if not _IDENTIFIER.fullmatch(experiment_id):
        raise ValueError(f".pithos.json experiment_id {experiment_id!r} must match {_IDENTIFIER.pattern!r}")
    micro_rush_id = project.get("micro_rush_id", project["experiment_id"])
    if not _IDENTIFIER.fullmatch(micro_rush_id):
        raise ValueError(f".pithos.json micro_rush_id {micro_rush_id!r} must match {_IDENTIFIER.pattern!r}")
    validation_command = project.get("validation_command")
    auto_oracle = not validation_command
    if auto_oracle and not project.get("target_files"):
        raise ValueError(
            ".pithos.json requires target_files to auto-author an oracle when validation_command is absent"
        )
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
    # placeholder command, replaced by OracleAuthor before the preflight gate ever runs it
    validator = CommandValidator(
        workspace,
        validation_command or ["python", "-c", "raise SystemExit(1)"],
        regression_command=project.get("regression_command"),
    )
    oracle_author = None
    if auto_oracle:
        oracle_author = OracleAuthor(
            configuration.model,
            project,
            workspace,
            mission_root / "oracle.py",
            validator,
        )
    seed = project.get("seed")
    # `seed` is the same opt-in signal used to gate next-rush proposal: a config that never asked for a
    # self-proposed next step hasn't asked for its PRs to be merged without a human looking either
    autonomous = isinstance(seed, str) and bool(seed.strip())
    next_rush_author = NextRushAuthor(configuration.model, project, workspace) if autonomous else None
    # decomposition only makes sense alongside an auto-authored oracle: a hand-written validation_command
    # was crafted by a human for the whole rush, splitting it up behind their back would break that contract
    todo_planner = TodoPlanner(configuration.model, project, workspace) if auto_oracle else None
    git_send = None
    if git_socket:
        git_send = lambda request: send_request(git_socket, request)
    finalizer = LocalFinalizer(workspace, mission_root, logs_root, git_send, auto_merge=autonomous)
    orchestrator = Orchestrator(
        state_store,
        phase_runner,
        validator,
        finalizer,
        oracle_author=oracle_author,
        next_rush_author=next_rush_author,
        todo_planner=todo_planner,
    )
    state = MissionState(
        mission_id,
        project["experiment_id"],
        micro_rush_id=micro_rush_id,
        phase="plan_todo" if auto_oracle else "preflight",
    )
    started_monotonic = time.monotonic()
    events.append(
        "run.started",
        {
            "experiment_id": state.experiment_id,
            "micro_rush_id": f"rush-{state.micro_rush_id}",
            "model": configuration.model,
            "oracle": "generated" if auto_oracle else "manual",
        },
    )
    _notify(telegram_socket, project, state, "started")

    target_snapshot = _snapshot_targets(workspace, project.get("target_files") or [])
    try:
        context_factory = ContextFactory(workspace, target_paths=project.get("target_files"), project=project)
        result = orchestrator.run(state, context_factory, max_steps=_MAX_ORCHESTRATOR_STEPS)
    except KeyboardInterrupt:
        _restore_targets(workspace, target_snapshot)
        orchestrator.interrupt(state, "operator interrupt")
        finish_payload = _finish_payload(state, mission_root, started_monotonic)
        events.append("run.finished", finish_payload)
        _notify(telegram_socket, project, state, "finished", finish_payload)
        raise
    except BaseException:
        _restore_targets(workspace, target_snapshot)
        raise
    if result.status != "completed":
        _restore_targets(workspace, target_snapshot)
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


def _snapshot_targets(workspace, relative_paths):
    """Capture the approved target files so a failed mission can be rolled back."""

    snapshot = {}
    for relative in relative_paths:
        path = Path(workspace) / relative
        snapshot[relative] = path.read_bytes() if path.is_file() else None

    return snapshot


def _restore_targets(workspace, snapshot):
    """Restore only configured targets changed by an unsuccessful mission."""

    for relative, content in snapshot.items():
        path = Path(workspace) / relative
        if content is None:
            path.unlink(missing_ok=True)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_bytes(content)
        temporary.replace(path)


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
    if state.todo:
        done = sum(1 for item in state.todo if item.get("status") == "done")
        details = f"{details}\nÉtapes : {done}/{len(state.todo)} validée(s)."
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
        "todo": [{"title": item["title"], "status": item.get("status", "pending")} for item in state.todo],
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
