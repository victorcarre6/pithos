#!/usr/bin/env python3
"""Launch one experiment run with the available host-side brokers."""

import argparse
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
from pithos_orchestrator.next_rush import NextRushAuthor
from pithos_orchestrator.state import MissionState
from pithos_runner.lock import LockHeld, RunLock


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
            else:
                previous_count = 0
                if failure_path.is_file():
                    previous = json.loads(failure_path.read_text(encoding="utf-8"))
                    if previous.get("micro_rush_id") == project.get("micro_rush_id"):
                        previous_count = previous.get("count", 0)
                failures = {"micro_rush_id": project.get("micro_rush_id"), "count": previous_count + 1}
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
    author = NextRushAuthor(project.get("model", "maternion/ling-3.0-tiny:8b"), project, workspace)
    success, reason = author(state)
    if not success:
        return {
            "status": "planning_failed",
            "reason": reason,
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

    return 0 if result["status"] in {"completed", "skipped"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
