#!/usr/bin/env python3
"""Prepare the non-secret host directories required by Pithos."""

import argparse
import json
import shutil
from pathlib import Path


COMMANDS = ("docker", "git", "node", "npm", "ollama", "pi")
PROJECT_DIRECTORIES = ("experiments", "journals/harness")
LOG_DIRECTORIES = ("archive/live", "network", "runs", "runtime", "telegram")
REQUIRED_PROJECT_FILES = (
    "ground_truth/AGENTS.md",
    "ground_truth/.pi/skills/pithos-continuity/SKILL.md",
    "runtime/docker-compose.yml",
    "dashboard/docker-compose.yml",
    "config/pi/models.json",
    "config/pi/settings.json",
    "config/pi-docker/models.json",
    "config/pi-docker/settings.json",
)


def inspect(project_root: Path, logs_root: Path) -> dict:
    """Return the local bootstrap state without changing it."""

    # fichiers contrôlés et commandes hôte
    missing_files = [path for path in REQUIRED_PROJECT_FILES if not (project_root / path).is_file()]
    missing_commands = [command for command in COMMANDS if shutil.which(command) is None]

    # emplacements persistants
    expected_directories = [project_root / path for path in PROJECT_DIRECTORIES]
    expected_directories.extend(logs_root / path for path in LOG_DIRECTORIES)
    missing_directories = [str(path) for path in expected_directories if not path.is_dir()]

    return {
        "project_root": str(project_root),
        "logs_root": str(logs_root),
        "missing_commands": missing_commands,
        "missing_files": missing_files,
        "missing_directories": missing_directories,
        "ready": not missing_commands and not missing_files and not missing_directories,
    }


def bootstrap(project_root: Path, logs_root: Path) -> dict:
    """Create only missing directories and the append-only live log."""

    # validation avant toute écriture
    state = inspect(project_root, logs_root)
    if state["missing_files"]:
        missing = ", ".join(state["missing_files"])
        raise RuntimeError(f"missing controlled project files: {missing}")

    for config_path in (project_root / "config").glob("*/models.json"):
        json.loads(config_path.read_text(encoding="utf-8"))
    for config_path in (project_root / "config").glob("*/settings.json"):
        json.loads(config_path.read_text(encoding="utf-8"))

    # arborescence locale sans remplacement
    for relative_path in PROJECT_DIRECTORIES:
        (project_root / relative_path).mkdir(parents=True, exist_ok=True)
    for relative_path in LOG_DIRECTORIES:
        (logs_root / relative_path).mkdir(parents=True, exist_ok=True)
    (logs_root / "live.log").touch(exist_ok=True)

    return inspect(project_root, logs_root)


def main() -> int:
    """Run the idempotent host bootstrap or inspect its current state."""

    parser = argparse.ArgumentParser(description="Prepare the Pithos host filesystem")
    parser.add_argument("--project-root", type=Path, default=Path(__file__).parents[1])
    parser.add_argument("--logs-root", type=Path, default=Path.home() / "logs" / "pithos")
    parser.add_argument("--check", action="store_true", help="inspect without writing")
    arguments = parser.parse_args()

    project_root = arguments.project_root.expanduser().resolve()
    logs_root = arguments.logs_root.expanduser().resolve()
    state = inspect(project_root, logs_root) if arguments.check else bootstrap(project_root, logs_root)

    print(json.dumps(state, indent=2))

    return 0 if state["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
