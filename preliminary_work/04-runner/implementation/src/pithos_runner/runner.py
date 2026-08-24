"""Orchestrate one isolated Pi run and persist its authoritative outcome."""

import json
import os
import secrets
import shutil
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pithos_capability_probe.runner import classify_protocol, parse_events
from pithos_continuity import publish_report
from pithos_contracts import validate_report
from pithos_harness import HarnessManager

from .events import EventWriter
from .lock import RunLock
from .process import run_monitored
from .pi_events import PiEventAdapter
from .state import read_state, write_state


LOOP_WARNING = "[WARNING] Boucle récursive infinie détectée."


def _notify(socket_path: Path | None, request: dict) -> None:
    """Send one runner-owned Telegram message without affecting the run."""

    if socket_path is None:
        return

    from pithos_telegram.client import send_request

    try:
        send_request(socket_path, request)
    except (OSError, RuntimeError, ValueError):
        pass


@dataclass(frozen=True)
class RunnerConfiguration:
    """Paths and bounded policies for one experiment runner."""

    experiment_id: str
    workspace: Path
    logs_root: Path
    pi_config_dir: Path
    pi_executable: str = "pi"
    runtime: str = "docker"
    docker_image: str = "pithos-agent:local"
    provider: str = "ollama"
    model: str = "maternion/ling-3.0-tiny:8b"
    timeout_seconds: int = 3600
    repeat_limit: int = 5
    heartbeat_seconds: float = 30
    git_socket: Path | None = None
    harness_socket: Path | None = None
    telegram_socket: Path | None = None
    ground_truth_root: Path | None = None
    harness_journals_root: Path | None = None


def new_run_id() -> str:
    now = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    return f"run-{now}-{secrets.token_hex(3)}"


def _write_run(path: Path, content: dict) -> None:
    temporary_path = path.with_suffix(".tmp")
    temporary_path.write_text(json.dumps(content, indent=2) + "\n", encoding="utf-8")
    temporary_path.replace(path)


def _host_environment() -> dict[str, str]:
    """Forward only non-secret process settings to the runtime launcher."""

    allowed = ("PATH", "TMPDIR", "LANG", "LC_ALL", "TERM")

    return {name: os.environ[name] for name in allowed if name in os.environ}


def _pi_arguments(configuration: RunnerConfiguration, session_dir: Path, prompt: str) -> list[str]:
    return [
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
        prompt,
    ]


def _runtime_command(
    configuration: RunnerConfiguration,
    run_id: str,
    run_dir: Path,
    prompt: str,
) -> tuple[list[str], dict[str, str]]:
    """Build either the Docker baseline or the explicit host test runtime."""

    environment = _host_environment()
    if configuration.runtime == "host":
        environment["PI_CODING_AGENT_DIR"] = str(configuration.pi_config_dir)
        environment["PITHOS_RUN_ID"] = run_id
        if configuration.git_socket:
            environment["PITHOS_GIT_SOCKET"] = str(configuration.git_socket)
        if configuration.harness_socket:
            environment["PITHOS_HARNESS_SOCKET"] = str(configuration.harness_socket)
        if configuration.telegram_socket:
            environment["PITHOS_TELEGRAM_SOCKET"] = str(configuration.telegram_socket)
        arguments = _pi_arguments(configuration, run_dir / "sessions", prompt)

        return [configuration.pi_executable, *arguments], environment
    if configuration.runtime != "docker":
        raise ValueError(f"unsupported runner runtime: {configuration.runtime}")
    _validate_pi_config(configuration.pi_config_dir)

    proxy_url = f"http://{run_id}@pithos-egress:3128"
    command = [
        "docker",
        "run",
        "--rm",
        "--name",
        f"pithos-{run_id}",
        "--network",
        "pithos-agent",
        "--read-only",
        "--tmpfs",
        "/tmp:rw,nosuid,nodev",
        "--mount",
        f"type=bind,src={configuration.workspace},dst=/workspace",
        "--mount",
        f"type=bind,src={run_dir},dst=/artifacts",
        "--mount",
        f"type=bind,src={configuration.pi_config_dir},dst=/pi-config-source,readonly",
        "--env",
        f"PITHOS_RUN_ID={run_id}",
        "--env",
        f"HTTP_PROXY={proxy_url}",
        "--env",
        f"HTTPS_PROXY={proxy_url}",
        "--env",
        f"ALL_PROXY={proxy_url}",
    ]
    if configuration.git_socket:
        command.extend(_socket_mount(configuration.git_socket, "/run/pithos/git.sock", "PITHOS_GIT_SOCKET"))
    if configuration.harness_socket:
        command.extend(
            _socket_mount(
                configuration.harness_socket,
                "/run/pithos/harness.sock",
                "PITHOS_HARNESS_SOCKET",
            )
        )
    if configuration.telegram_socket:
        command.extend(
            _socket_mount(
                configuration.telegram_socket,
                "/run/pithos/telegram.sock",
                "PITHOS_TELEGRAM_SOCKET",
            )
        )
    arguments = _pi_arguments(configuration, Path("/artifacts/sessions"), prompt)
    command.extend([configuration.docker_image, *arguments])

    return command, environment


def _validate_pi_config(config_dir: Path) -> None:
    sensitive_names = ("auth", "credential", "secret", "token", ".env")
    sensitive = [
        path
        for path in config_dir.rglob("*")
        if path.is_file() and any(marker in path.name.lower() for marker in sensitive_names)
    ]
    if sensitive:
        names = ", ".join(path.name for path in sensitive)
        raise ValueError(f"Pi config contains files forbidden in the agent runtime: {names}")


def _socket_mount(source: Path, target: str, environment_name: str) -> list[str]:
    return [
        "--mount",
        f"type=bind,src={source},dst={target}",
        "--env",
        f"{environment_name}={target}",
    ]


def _cleanup_runtime(configuration: RunnerConfiguration, run_id: str) -> None:
    if configuration.runtime != "docker":
        return

    result = subprocess.run(
        ["docker", "rm", "--force", f"pithos-{run_id}"],
        env=_host_environment(),
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    if result.returncode not in {0, 1}:
        raise RuntimeError("failed to remove interrupted Pi container")


def _claim_telegram_answers(logs_root: Path, run_dir: Path, continuity_dir: Path) -> None:
    """Atomically move pending user answers into this run and its Pi context."""

    pending_path = logs_root / "runtime" / "answers.jsonl"
    context_path = continuity_dir / "ANSWERS.jsonl"
    context_path.unlink(missing_ok=True)
    if not pending_path.exists():
        return

    archive_path = run_dir / "telegram-answers.jsonl"
    pending_path.replace(archive_path)
    shutil.copy2(archive_path, context_path)


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
        pi_adapter = PiEventAdapter(EventWriter(run_dir / "events.jsonl", run_id, source="pi"))
        harness_manager = None
        if configuration.ground_truth_root and configuration.harness_journals_root:
            harness_manager = HarnessManager(
                configuration.workspace,
                configuration.ground_truth_root,
                configuration.harness_journals_root,
                configuration.logs_root,
            )
            harness_manager.begin(run_id)
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
            "session_id": None,
            "commit_before": None,
            "commit_after": None,
            "artifacts_dir": f"runs/{run_id}",
            "stop_reason": None,
            "success": {"process": None, "protocol": None, "task": None, "report": None},
        }
        _write_run(run_dir / "run.json", run_document)
        events.append(
            "run.started",
            {
                "experiment_id": configuration.experiment_id,
                "micro_rush_id": None,
                "model": configuration.model,
            },
        )
        _notify(
            configuration.telegram_socket,
            {
                "request_id": f"{run_id}-started",
                "run_id": run_id,
                "kind": "INFO",
                "text": f"Run démarré : {configuration.experiment_id} ({run_id}).",
            },
        )

        latest_path = configuration.logs_root / "latest.md"
        continuity_dir = configuration.workspace / ".pithos"
        continuity_dir.mkdir(exist_ok=True)
        if latest_path.exists():
            shutil.copy2(latest_path, continuity_dir / "LATEST.md")
        _claim_telegram_answers(configuration.logs_root, run_dir, continuity_dir)

        report_path = continuity_dir / "report.md"
        report_path.unlink(missing_ok=True)
        session_dir = run_dir / "sessions"
        session_dir.mkdir()
        prompt = (
            "Read PROJECT.md first, then .pithos/LATEST.md and .pithos/ANSWERS.jsonl only when they exist. "
            "Implement one TODO micro-rush directly without exhaustive workspace inventory or dependency "
            "installation. Run its tests, use pithos_git for branch, commit, push and PR, notify meaningful "
            "outcomes, then write the validated continuity report to .pithos/report.md before finishing."
        )
        command, environment = _runtime_command(configuration, run_id, run_dir, prompt)
        try:
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
                stop_requested=lambda: read_state(state_path)["paused"],
                on_loop_detected=lambda: _notify(
                    configuration.telegram_socket,
                    {
                        "request_id": f"{run_id}-loop-guard",
                        "run_id": run_id,
                        "kind": "WARNING",
                        "text": "Boucle récursive infinie détectée.",
                    },
                ),
                on_stdout_line=pi_adapter.consume_line,
                on_forced_stop=lambda: _cleanup_runtime(configuration, run_id),
            )
        except KeyboardInterrupt:
            run_document["status"] = "interrupted"
            run_document["finished_at"] = datetime.now(UTC).isoformat()
            run_document["stop_reason"] = "operator interrupt"
            run_document["success"] = {
                "process": False,
                "protocol": None,
                "task": None,
                "report": False,
            }
            _write_run(run_dir / "run.json", run_document)
            events.append("run.finished", {"status": "interrupted", "stop_reason": "operator interrupt"})
            _notify(
                configuration.telegram_socket,
                {
                    "request_id": f"{run_id}-finished",
                    "run_id": run_id,
                    "kind": "WARNING",
                    "text": (
                        f"Run terminé : {configuration.experiment_id} ({run_id}), "
                        "statut=interrupted. Raison : operator interrupt"
                    ),
                },
            )
            raise

        stdout = (run_dir / "stdout.jsonl").read_text(encoding="utf-8")
        pi_events, parse_errors = parse_events(stdout)
        protocol_success, _ = classify_protocol(pi_events, parse_errors)
        session_event = next((event for event in pi_events if event.get("type") == "session"), None)
        if session_event:
            run_document["session_id"] = session_event.get("id")

        report_success = False
        task_success = None
        report_metadata = None
        if report_path.exists():
            try:
                report_metadata = validate_report(report_path)
                publish_report(report_path, configuration.logs_root)
                report_success = True
            except (OSError, ValueError):
                report_success = False
        if report_metadata:
            task_success = report_metadata["status"] == "completed"
            for field in ("micro_rush_id", "branch", "commit_before", "commit_after"):
                run_document[field] = report_metadata.get(field)

        if outcome.loop_detected:
            status = "paused"
            stop_reason = LOOP_WARNING
            write_state(state_path, True, stop_reason)
            events.append(
                "run.loop_detected",
                {"repeated_signature": outcome.repeated_signature},
            )
        elif outcome.externally_stopped:
            status = "paused"
            stop_reason = read_state(state_path)["reason"]
        elif outcome.timed_out:
            status = "timed_out"
            stop_reason = "run exceeded its configured timeout"
        elif outcome.exit_code == 0 and report_success:
            status = report_metadata["status"]
            stop_reason = report_metadata.get("stop_reason")
        else:
            status = "failed"
            stop_reason = "Pi failed or did not publish a valid report"

        run_document["status"] = status
        run_document["finished_at"] = datetime.now(UTC).isoformat()
        run_document["stop_reason"] = stop_reason
        run_document["success"] = {
            "process": outcome.exit_code == 0,
            "protocol": protocol_success,
            "task": task_success,
            "report": report_success,
        }
        _write_run(run_dir / "run.json", run_document)
        events.append(
            "run.finished",
            {
                "status": status,
                "stop_reason": stop_reason,
                "session_id": run_document["session_id"],
                "duration_ms": round(outcome.duration_seconds * 1000),
                **pi_adapter.metrics(),
            },
        )
        completion_kind = "INFO" if status == "completed" else "WARNING"
        completion_text = f"Run terminé : {configuration.experiment_id} ({run_id}), statut={status}."
        if stop_reason:
            completion_text = f"{completion_text} Raison : {stop_reason}"
        _notify(
            configuration.telegram_socket,
            {
                "request_id": f"{run_id}-finished",
                "run_id": run_id,
                "kind": completion_kind,
                "text": completion_text,
            },
        )
        if harness_manager:
            validation = json.dumps(run_document["success"], sort_keys=True)
            rationale = stop_reason or "Run completed and harness state was captured."
            harness_manager.finish(run_id, rationale, validation)

        return run_document
