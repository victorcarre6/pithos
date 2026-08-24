#!/usr/bin/env python3
"""Install user LaunchAgents for one Pithos experiment."""

import argparse
import json
import os
import plistlib
import re
import subprocess
from pathlib import Path


EXPERIMENT_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
LAUNCH_PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"


def definitions(harness_root, workspace, logs_root, interval_seconds, home):
    """Build the runner and collector LaunchAgent definitions."""

    # chemins absolus contrôlés
    harness_root = Path(harness_root).resolve()
    workspace = Path(workspace).resolve()
    logs_root = Path(logs_root).expanduser().resolve()
    project = plist_project(workspace)
    experiment_id = project["experiment_id"]
    python = harness_root / ".venv" / "bin" / "python"
    environment = {
        "HOME": str(Path(home).resolve()),
        "PATH": LAUNCH_PATH,
        "PYTHONUNBUFFERED": "1",
    }

    # collecteur permanent
    collector_label = "dev.pithos.events"
    collector = {
        "Label": collector_label,
        "ProgramArguments": [
            str(python),
            "-m",
            "pithos_event_store.cli",
            "--logs-root",
            str(logs_root),
            "--interval-seconds",
            "5",
            "watch",
        ],
        "WorkingDirectory": str(harness_root),
        "EnvironmentVariables": environment,
        "RunAtLoad": True,
        "KeepAlive": True,
        "StandardOutPath": str(logs_root / "runtime" / "launchd-events.stdout.log"),
        "StandardErrorPath": str(logs_root / "runtime" / "launchd-events.stderr.log"),
    }

    # réveil borné de l'expérience
    runner_label = f"dev.pithos.runner.{experiment_id}"
    runner = {
        "Label": runner_label,
        "ProgramArguments": [
            str(python),
            str(harness_root / "scripts" / "run_experiment.py"),
            str(workspace),
            "--logs-root",
            str(logs_root),
        ],
        "WorkingDirectory": str(workspace),
        "EnvironmentVariables": environment,
        "StartInterval": interval_seconds,
        "StandardOutPath": str(logs_root / "runtime" / "launchd-runner.stdout.log"),
        "StandardErrorPath": str(logs_root / "runtime" / "launchd-runner.stderr.log"),
    }

    return {
        collector_label: collector,
        runner_label: runner,
    }


def plist_project(workspace):
    """Read and validate the experiment identity used in launchd labels."""

    project = json.loads((Path(workspace) / ".pithos.json").read_text(encoding="utf-8"))
    experiment_id = project.get("experiment_id", "")
    if not EXPERIMENT_PATTERN.fullmatch(experiment_id):
        raise ValueError("experiment_id is not safe for a launchd label")

    return project


def write_plists(items, agents_dir):
    """Atomically write private plist files and return their paths."""

    agents_dir = Path(agents_dir).expanduser().resolve()
    agents_dir.mkdir(parents=True, exist_ok=True)
    paths = {}
    for label, content in items.items():
        path = agents_dir / f"{label}.plist"
        temporary = path.with_suffix(".tmp")
        with temporary.open("wb") as plist_file:
            plistlib.dump(content, plist_file, sort_keys=False)
        os.chmod(temporary, 0o600)
        temporary.replace(path)
        paths[label] = path

    return paths


def install(paths, uid):
    """Replace and bootstrap the rendered LaunchAgents in the user domain."""

    domain = f"gui/{uid}"
    for label, path in paths.items():
        subprocess.run(
            ["launchctl", "bootout", domain, str(path)],
            capture_output=True,
            text=True,
            check=False,
        )
        subprocess.run(["launchctl", "bootstrap", domain, str(path)], check=True)
        subprocess.run(["launchctl", "enable", f"{domain}/{label}"], check=True)


def uninstall(labels, agents_dir, uid):
    """Unload and remove only the Pithos plist files selected by label."""

    domain = f"gui/{uid}"
    agents_dir = Path(agents_dir).expanduser().resolve()
    for label in labels:
        path = agents_dir / f"{label}.plist"
        subprocess.run(
            ["launchctl", "bootout", domain, str(path)],
            capture_output=True,
            text=True,
            check=False,
        )
        path.unlink(missing_ok=True)


def main():
    """Render, install or uninstall the two user LaunchAgents."""

    parser = argparse.ArgumentParser(description="Manage Pithos user LaunchAgents")
    parser.add_argument("action", choices=("render", "install", "uninstall"))
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--logs-root", type=Path, default=Path.home() / "logs" / "pithos")
    parser.add_argument("--interval-seconds", type=int, default=10_800)
    parser.add_argument("--agents-dir", type=Path, default=Path.home() / "Library" / "LaunchAgents")
    arguments = parser.parse_args()
    if arguments.interval_seconds < 300:
        parser.error("--interval-seconds must be at least 300")

    harness_root = Path(__file__).resolve().parents[1]
    items = definitions(
        harness_root,
        arguments.workspace,
        arguments.logs_root,
        arguments.interval_seconds,
        Path.home(),
    )
    if arguments.action == "uninstall":
        uninstall(items, arguments.agents_dir, os.getuid())

        return 0

    paths = write_plists(items, arguments.agents_dir)
    if arguments.action == "install":
        install(paths, os.getuid())
    for path in paths.values():
        print(path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
