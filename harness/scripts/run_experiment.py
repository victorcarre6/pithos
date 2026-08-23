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

from pithos_runner.runner import RunnerConfiguration, run_once


def configuration_for(workspace: Path, logs_root: Path, sockets: dict):
    """Build the runner configuration from one generated experiment."""

    project = json.loads((workspace / ".pithos.json").read_text(encoding="utf-8"))
    ground_truth = Path(project["ground_truth"]).resolve()
    harness_root = ground_truth.parent
    repository_root = workspace.parent.parent

    return RunnerConfiguration(
        experiment_id=project["experiment_id"],
        workspace=workspace,
        logs_root=logs_root,
        pi_config_dir=Path(project["pi_config"]).resolve(),
        runtime=project.get("runtime", "docker"),
        git_socket=sockets.get("git"),
        harness_socket=sockets.get("harness"),
        telegram_socket=sockets.get("telegram"),
        ground_truth_root=ground_truth,
        harness_journals_root=repository_root / "journals" / "harness",
    )


def launch(workspace: Path, logs_root: Path):
    """Start optional brokers, execute one run and retain all service logs."""

    workspace = workspace.resolve()
    logs_root = logs_root.expanduser().resolve()
    project = json.loads((workspace / ".pithos.json").read_text(encoding="utf-8"))
    harness_root = Path(project["ground_truth"]).resolve().parent
    runtime_root = logs_root / "runtime"
    runtime_root.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment["PITHOS_LOGS_ROOT"] = str(logs_root)
    subprocess.run(
        ["docker", "compose", "-f", str(harness_root / "runtime" / "docker-compose.yml"), "up", "-d"],
        check=True,
        env=environment,
    )

    processes = []
    sockets = {}
    with ExitStack() as stack:
        harness_socket = runtime_root / f"{project['experiment_id']}-harness.sock"
        harness_command = [
            sys.executable,
            "-m",
            "pithos_harness.cli",
            "--active-root",
            str(workspace),
            "--ground-truth-root",
            str(harness_root / "ground_truth"),
            "--journals-root",
            str(workspace.parent.parent / "journals" / "harness"),
            "--logs-root",
            str(logs_root),
            "serve",
            "--socket",
            str(harness_socket),
        ]
        processes.append(_start_broker(harness_command, harness_socket, runtime_root, "harness", stack))
        sockets["harness"] = harness_socket

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
            processes.append(_start_broker(git_command, git_socket, runtime_root, "git", stack))
            sockets["git"] = git_socket

        if os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_USER_ID"):
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
            processes.append(_start_broker(telegram_command, telegram_socket, runtime_root, "telegram", stack))
            sockets["telegram"] = telegram_socket

        try:
            return run_once(configuration_for(workspace, logs_root, sockets))
        finally:
            for process in reversed(processes):
                process.terminate()
            for process in reversed(processes):
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()


def _start_broker(command, socket_path, runtime_root, name, stack):
    """Start one broker and wait until its private socket accepts connections."""

    if socket_path.exists():
        socket_path.unlink()
    stdout = stack.enter_context((runtime_root / f"{name}.stdout.log").open("a", encoding="utf-8"))
    stderr = stack.enter_context((runtime_root / f"{name}.stderr.log").open("a", encoding="utf-8"))
    process = subprocess.Popen(command, stdout=stdout, stderr=stderr, text=True)
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
