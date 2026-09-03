#!/usr/bin/env python3
"""Launch one experiment run with the available host-side brokers."""

import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
import time
from contextlib import ExitStack
from datetime import UTC, datetime
from pathlib import Path

from pithos_orchestrator.launcher import launch as launch_orchestrated
from pithos_orchestrator.next_rush import NextRushAuthor, roadmap_complete
from pithos_orchestrator.state import MissionState
from pithos_runner.events import EventWriter
from pithos_runner.lock import LockHeld, RunLock
from pithos_runner.runner import new_run_id
from pithos_telegram import TelegramBroker
from pithos_telegram.api import TelegramAPI


# au-delà, un micro-rush bloqué (proposition redondante, oracle inatteignable, etc.) retentait
# indéfiniment à chaque réveil du LaunchAgent sans jamais avancer -- observé sur frame-pipeline-v2
MAX_CONSECUTIVE_FAILURES = 3
DOCKER_START_TIMEOUT_SECONDS = 120


def launch(workspace: Path, logs_root: Path):
    """Start optional brokers, execute one run and retain all service logs."""

    workspace = workspace.resolve()
    logs_root = logs_root.expanduser().resolve()
    project = json.loads((workspace / ".pithos.json").read_text(encoding="utf-8"))
    harness_root = Path(project["ground_truth"]).resolve().parent
    runtime_root = logs_root / "runtime"
    runtime_root.mkdir(parents=True, exist_ok=True)
    host_environment = os.environ.copy()
    host_environment["PITHOS_LOGS_ROOT"] = str(logs_root)
    telegram_environment = _environment_for(workspace, logs_root)
    processes = []
    sockets = {}
    with ExitStack() as stack:
        stack.enter_context(RunLock(runtime_root / f"{project['experiment_id']}.lock"))

        # récupération des checkpoints qu'une ancienne sortie brutale a laissés actifs
        recovered = _reconcile_stale_runs(logs_root, project["experiment_id"])

        # une roadmap achevée produit une proposition d'arrêt unique, jamais un rush inventé
        stop_path = runtime_root / f"{project['experiment_id']}-stop-proposal.json"
        roadmap_path = workspace / "docs" / "ROADMAP.md"
        roadmap_content = roadmap_path.read_text(encoding="utf-8") if roadmap_path.is_file() else ""
        roadmap_sha256 = hashlib.sha256(roadmap_content.encode()).hexdigest()
        if stop_path.is_file():
            stop = json.loads(stop_path.read_text(encoding="utf-8"))
            if stop.get("roadmap_sha256") == roadmap_sha256:
                return {
                    "status": "skipped",
                    "reason": "project stop already proposed",
                    "micro_rush_id": project.get("micro_rush_id"),
                    "run_id": stop.get("run_id"),
                    "recovered_missions": recovered,
                }

        seed = project.get("seed")
        autonomous = isinstance(seed, str) and bool(seed.strip())
        if autonomous and roadmap_complete(workspace, content=roadmap_content):
            advanced = _advance_autonomous_rush(workspace, project, "project roadmap completed")
            if advanced["status"] == "stop_proposed":
                result = _publish_stop_proposal(
                    workspace,
                    logs_root,
                    project,
                    stop_path,
                    roadmap_sha256,
                    telegram_environment,
                    advanced["reason"],
                )
                result["recovered_missions"] = recovered

                return result

        # un micro-rush réussi ne se répète pas ; une campagne autonome choisit puis lance le suivant
        completion_path = runtime_root / f"{project['experiment_id']}-completed.json"
        if completion_path.is_file():
            completion = json.loads(completion_path.read_text(encoding="utf-8"))
            if completion.get("micro_rush_id") == project.get("micro_rush_id"):
                advanced = _advance_autonomous_rush(workspace, project, "previous micro-rush completed")
                if advanced is None:
                    return {
                        "status": "skipped",
                        "reason": "micro-rush already completed",
                        "micro_rush_id": project.get("micro_rush_id"),
                        "mission_id": completion.get("mission_id"),
                    }
                if advanced["status"] != "advanced":
                    return advanced
                project = advanced["project"]

        # un rush autonome bloqué est remplacé ; une campagne supervisée conserve l'arrêt historique
        failure_path = runtime_root / f"{project['experiment_id']}-failures.json"
        if failure_path.is_file():
            failures = json.loads(failure_path.read_text(encoding="utf-8"))
            if (
                failures.get("micro_rush_id") == project.get("micro_rush_id")
                and failures.get("count", 0) >= MAX_CONSECUTIVE_FAILURES
            ):
                advanced = _advance_autonomous_rush(workspace, project, "previous micro-rush repeatedly failed")
                if advanced is None:
                    return {
                        "status": "skipped",
                        "reason": "micro-rush failed too many times in a row; needs human intervention",
                        "micro_rush_id": project.get("micro_rush_id"),
                        "consecutive_failures": failures.get("count", 0),
                    }
                if advanced["status"] != "advanced":
                    return advanced
                project = advanced["project"]

        if project.get("runtime", "docker") == "docker":
            subprocess.run(
                ["docker", "compose", "-f", str(harness_root / "runtime" / "docker-compose.yml"), "up", "-d"],
                check=True,
                env=host_environment,
                timeout=DOCKER_START_TIMEOUT_SECONDS,
            )

        remote = _git_remote(workspace)
        if remote:
            git_socket = runtime_root / f"{project['experiment_id']}-git.sock"
            git_command = [
                sys.executable,
                "-m",
                "pithos_git_broker.cli",
                "--repository",
                str(workspace),
                "--remote",
                remote,
                "--socket",
                str(git_socket),
                "--logs-root",
                str(logs_root),
            ]
            processes.append(
                _start_broker(git_command, git_socket, runtime_root, "git", stack, host_environment)
            )
            sockets["git"] = git_socket

        if telegram_environment.get("TELEGRAM_BOT_TOKEN") and telegram_environment.get("TELEGRAM_USER_ID"):
            telegram_socket = runtime_root / f"{project['experiment_id']}-telegram.sock"
            telegram_command = [
                sys.executable,
                "-m",
                "pithos_telegram.cli",
                "serve",
                "--socket",
                str(telegram_socket),
                "--logs-root",
                str(logs_root),
            ]
            processes.append(
                _start_broker(
                    telegram_command,
                    telegram_socket,
                    runtime_root,
                    "telegram",
                    stack,
                    telegram_environment,
                )
            )
            sockets["telegram"] = telegram_socket

        try:
            state = launch_orchestrated(
                workspace,
                logs_root,
                sockets.get("git"),
                sockets.get("telegram"),
            )
            result = state.__dict__
            if state.status == "completed":
                completion = {
                    "micro_rush_id": state.micro_rush_id,
                    "mission_id": state.mission_id,
                    "completed_at": datetime.now(UTC).isoformat(),
                }
                temporary = completion_path.with_suffix(".tmp")
                temporary.write_text(json.dumps(completion, indent=2) + "\n", encoding="utf-8")
                temporary.replace(completion_path)
                failure_path.unlink(missing_ok=True)
                stop_reason = getattr(state, "artifacts", {}).get("stop_proposal")
                if stop_reason:
                    completed_roadmap = roadmap_path.read_text(encoding="utf-8")
                    completed_sha256 = hashlib.sha256(completed_roadmap.encode()).hexdigest()
                    stop_result = _publish_stop_proposal(
                        workspace,
                        logs_root,
                        project,
                        stop_path,
                        completed_sha256,
                        telegram_environment,
                        stop_reason,
                    )
                    result["stop_proposal"] = stop_result
            else:
                previous_count = 0
                if failure_path.is_file():
                    previous = json.loads(failure_path.read_text(encoding="utf-8"))
                    if previous.get("micro_rush_id") == project.get("micro_rush_id"):
                        previous_count = previous.get("count", 0)
                failures = {
                    "micro_rush_id": project.get("micro_rush_id"),
                    "mission_id": state.mission_id,
                    "count": previous_count + 1,
                }
                temporary = failure_path.with_suffix(".tmp")
                temporary.write_text(json.dumps(failures, indent=2) + "\n", encoding="utf-8")
                temporary.replace(failure_path)

            return result
        finally:
            for process in reversed(processes):
                process.terminate()
            for process in reversed(processes):
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()


def _advance_autonomous_rush(workspace, project, trigger):
    """Author and load the next rush, or return None for a non-autonomous project."""

    seed = project.get("seed")
    if not isinstance(seed, str) or not seed.strip():
        return None

    # le handoff n'ouvre aucun broker : il ne fait qu'une proposition locale bornée
    state = MissionState(
        "handoff",
        project["experiment_id"],
        micro_rush_id=project.get("micro_rush_id", ""),
        changed_files=list(project.get("target_files") or []),
    )
    if trigger == "previous micro-rush repeatedly failed" and project.get("target_function"):
        state.artifacts["avoid_target_functions"] = [project["target_function"]]
    author = NextRushAuthor(project.get("model", "maternion/ling-3.0-tiny:8b"), project, workspace)
    success, reason = author(state)
    if not success:
        return {
            "status": "planning_failed",
            "reason": reason,
            "trigger": trigger,
            "micro_rush_id": project.get("micro_rush_id"),
        }
    if state.artifacts.get("stop_proposal"):
        return {
            "status": "stop_proposed",
            "reason": state.artifacts["stop_proposal"],
            "trigger": trigger,
            "micro_rush_id": project.get("micro_rush_id"),
        }

    updated = json.loads((workspace / ".pithos.json").read_text(encoding="utf-8"))

    return {
        "status": "advanced",
        "reason": reason,
        "trigger": trigger,
        "project": updated,
    }


def _publish_stop_proposal(
    workspace,
    logs_root,
    project,
    stop_path,
    roadmap_sha256,
    telegram_environment,
    reason,
):
    """Validate project state, emit one stop proposal and persist its idempotence marker."""

    # preuve produit avant terminaison
    command = list(project.get("regression_command") or [])
    if command and command[0] == "python":
        command[0] = sys.executable
    if command:
        validation = subprocess.run(
            command,
            cwd=workspace,
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        if validation.returncode != 0:
            return {
                "status": "completion_check_failed",
                "reason": "project roadmap is done but regression validation failed",
                "micro_rush_id": project.get("micro_rush_id"),
                "validation_stdout": validation.stdout[-2000:],
                "validation_stderr": validation.stderr[-2000:],
            }

    # événement terminal observable
    run_id = new_run_id()
    events_path = logs_root / "runs" / run_id / "events.jsonl"
    events = EventWriter(events_path, run_id, source="campaign-controller")
    events.append(
        "run.started",
        {
            "experiment_id": project["experiment_id"],
            "micro_rush_id": f"rush-{project.get('micro_rush_id', project['experiment_id'])}",
            "model": project.get("model"),
        },
    )

    # notification brokerisée et best-effort
    notification = "not configured"
    token = telegram_environment.get("TELEGRAM_BOT_TOKEN")
    user_id = telegram_environment.get("TELEGRAM_USER_ID")
    if token and user_id:
        request = {
            "request_id": f"{project['experiment_id']}-project-stop-proposal",
            "run_id": run_id,
            "kind": "STOP_PROPOSAL",
            "text": (
                f"Projet {project['experiment_id']} terminé. "
                "Tous les éléments déclarés dans la roadmap sont DONE et la validation produit passe. "
                "Pithos propose l'arrêt de la campagne autonome."
            ),
        }
        try:
            api = TelegramAPI(token)
            broker = TelegramBroker(api, user_id, logs_root)
            response = broker.send(request)
            notification = "duplicate" if response.get("duplicate") else "sent"
        except RuntimeError as error:
            notification = f"failed: {error}"

    events.append(
        "run.finished",
        {
            "status": "completed",
            "stop_reason": reason,
            "duration_ms": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "tool_calls": 0,
            "tool_failures": 0,
        },
    )
    _write_stop_marker(
        stop_path,
        run_id,
        project.get("micro_rush_id"),
        roadmap_sha256,
        reason,
        notification,
    )

    return {
        "status": "stop_proposed",
        "reason": reason,
        "micro_rush_id": project.get("micro_rush_id"),
        "run_id": run_id,
        "notification": notification,
    }


def _write_stop_marker(path, run_id, micro_rush_id, roadmap_sha256, reason, notification):
    """Atomically persist one stop proposal bound to the roadmap content."""

    marker = {
        "run_id": run_id,
        "micro_rush_id": micro_rush_id,
        "roadmap_sha256": roadmap_sha256,
        "reason": reason,
        "notification": notification,
        "proposed_at": datetime.now(UTC).isoformat(),
    }
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(marker, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _reconcile_stale_runs(logs_root, experiment_id):
    """Append terminal evidence for checkpoints left running while this run owns the experiment lock."""

    recovered = []
    missions_root = Path(logs_root) / "missions"
    for state_path in sorted(missions_root.glob("*/state.json")):
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if state.get("experiment_id") != experiment_id or state.get("status") != "running":
            continue

        mission_id = state.get("mission_id", state_path.parent.name)
        reason = "runner exited without a terminal checkpoint; recovered before the next launch"
        previous_failure = str(state.get("failure_summary") or "").strip()
        if previous_failure:
            state["failure_summary"] = f"{previous_failure}\n{reason}"
        else:
            state["failure_summary"] = reason
        state["phase"] = "interrupted"
        state["status"] = "interrupted"
        state["updated_at"] = datetime.now(UTC).isoformat()
        state.setdefault("history", []).append(
            {
                "phase": "interrupted",
                "event": reason,
                "at": state["updated_at"],
            }
        )
        temporary = state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        temporary.replace(state_path)

        events_path = state_path.parent / "events.jsonl"
        EventWriter(events_path, mission_id, source="campaign-controller").append(
            "run.finished",
            {
                "status": "interrupted",
                "stop_reason": reason,
            },
        )
        recovered.append(mission_id)

    runs_root = Path(logs_root) / "runs"
    for run_path in sorted(runs_root.glob("*/run.json")):
        run = json.loads(run_path.read_text(encoding="utf-8"))
        if run.get("experiment_id") != experiment_id or run.get("status") != "running":
            continue

        run_id = run.get("run_id", run_path.parent.name)
        reason = "runner exited without a terminal document; recovered before the next launch"
        run["status"] = "interrupted"
        run["finished_at"] = datetime.now(UTC).isoformat()
        run["stop_reason"] = reason
        run["success"] = {
            "process": False,
            "protocol": run.get("success", {}).get("protocol"),
            "task": run.get("success", {}).get("task"),
            "report": run.get("success", {}).get("report"),
        }
        temporary = run_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(run, indent=2) + "\n", encoding="utf-8")
        temporary.replace(run_path)

        events_path = run_path.parent / "events.jsonl"
        EventWriter(events_path, run_id, source="campaign-controller").append(
            "run.finished",
            {
                "status": "interrupted",
                "stop_reason": reason,
            },
        )
        recovered.append(run_id)

    return recovered


def _environment_for(workspace, logs_root):
    """Load only the two Telegram credentials from the ignored workspace file."""

    # environnement hôte + chemin d'état
    environment = os.environ.copy()
    environment["PITHOS_LOGS_ROOT"] = str(logs_root)

    # valeurs Telegram explicites, sans écraser l'environnement hôte
    dotenv_path = Path(workspace) / ".env"
    if not dotenv_path.is_file():
        return environment

    allowed = {"TELEGRAM_BOT_TOKEN", "TELEGRAM_USER_ID"}
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        name, separator, raw_value = raw_line.strip().partition("=")
        if not separator or name not in allowed:
            continue
        value = raw_value.strip().strip("'\"")
        environment.setdefault(name, value)

    return environment


def _start_broker(command, socket_path, runtime_root, name, stack, environment):
    """Start one broker and wait until its private socket accepts connections."""

    if socket_path.exists():
        socket_path.unlink()
    stdout = stack.enter_context((runtime_root / f"{name}.stdout.log").open("a", encoding="utf-8"))
    stderr = stack.enter_context((runtime_root / f"{name}.stderr.log").open("a", encoding="utf-8"))
    process = subprocess.Popen(command, stdout=stdout, stderr=stderr, text=True, env=environment)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"{name} broker exited with {process.returncode}")
        if _socket_ready(socket_path):
            return process
        time.sleep(0.05)
    process.terminate()
    raise RuntimeError(f"{name} broker did not create {socket_path}")


def _socket_ready(path):
    """Check a Unix socket by connecting rather than trusting its path."""

    if not path.exists():
        return False
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(0.1)
    try:
        client.connect(str(path))
    except OSError:
        return False
    finally:
        client.close()

    return True


def _git_remote(workspace):
    """Return origin only when the user has configured a remote."""

    result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=workspace,
        capture_output=True,
        text=True,
    )

    return result.stdout.strip() if result.returncode == 0 else None


def main():
    """Launch one supervised autonomous run."""

    parser = argparse.ArgumentParser(description="Launch one Pithos experiment run")
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--logs-root", type=Path, default=Path.home() / "logs" / "pithos")
    arguments = parser.parse_args()
    try:
        result = launch(arguments.workspace, arguments.logs_root)
    except LockHeld as error:
        print(f"Run skipped: {error}")

        return 0
    print(json.dumps(result, indent=2))

    return 0 if result["status"] in {"completed", "skipped", "stop_proposed"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
