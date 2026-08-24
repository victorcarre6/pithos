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
from pathlib import Path

from pithos_orchestrator.launcher import launch as launch_orchestrated


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
    if project.get("runtime", "docker") == "docker":
        subprocess.run(
            ["docker", "compose", "-f", str(harness_root / "runtime" / "docker-compose.yml"), "up", "-d"],
            check=True,
            env=host_environment,
        )

    processes = []
    sockets = {}
    with ExitStack() as stack:
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
            return launch_orchestrated(
                workspace,
                logs_root,
                sockets.get("git"),
                sockets.get("telegram"),
            ).__dict__
        finally:
            for process in reversed(processes):
                process.terminate()
            for process in reversed(processes):
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()


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
    result = launch(arguments.workspace, arguments.logs_root)
    print(json.dumps(result, indent=2))

    return 0 if result["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
