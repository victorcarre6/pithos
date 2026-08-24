#!/usr/bin/env python3
"""Create one isolated experiment from the active Pithos ground truth."""

import argparse
import json
import re
import shutil
from pathlib import Path


EXPERIMENT_ID = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")


def create_experiment(harness_root: Path, experiments_root: Path, experiment_id: str, remote=None):
    """Create one experiment inside the repository containing experiments_root."""

    if not EXPERIMENT_ID.fullmatch(experiment_id):
        raise ValueError("experiment id must be a lowercase slug of 2 to 63 characters")
    target = experiments_root / experiment_id
    if target.exists():
        raise FileExistsError(target)

    template = harness_root / "templates" / "experiment"
    ground_truth = harness_root / "ground_truth"
    if not template.is_dir() or not ground_truth.is_dir():
        raise FileNotFoundError("harness template or ground truth is missing")

    shutil.copytree(template, target)
    shutil.copy2(ground_truth / "AGENTS.md", target / "AGENTS.md")
    shutil.copytree(ground_truth / ".pi", target / ".pi")
    configuration = {
        "schema_version": 1,
        "experiment_id": experiment_id,
        "title": experiment_id.replace("-", " ").capitalize(),
        "description": "Décrire ici le prochain micro-rush en une phrase.",
        "runtime": "docker",
        "pi_config": str(harness_root / "config" / "pi-docker"),
        "ground_truth": str(ground_truth),
    }
    (target / ".pithos.json").write_text(json.dumps(configuration, indent=2) + "\n", encoding="utf-8")
    if remote:
        raise ValueError("experiments use the parent repository remote")

    return target


def main():
    """Create one experiment selected explicitly by the user."""

    parser = argparse.ArgumentParser(description="Create an autonomous Pithos experiment")
    parser.add_argument("experiment_id")
    parser.add_argument("--harness-root", type=Path, default=Path(__file__).parents[1])
    parser.add_argument("--experiments-root", type=Path, default=Path(__file__).parents[2] / "experiments")
    parser.add_argument("--remote")
    arguments = parser.parse_args()
    target = create_experiment(
        arguments.harness_root.expanduser().resolve(),
        arguments.experiments_root.expanduser().resolve(),
        arguments.experiment_id,
        arguments.remote,
    )
    print(target)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
