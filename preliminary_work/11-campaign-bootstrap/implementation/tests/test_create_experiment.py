import importlib.util
import json
import subprocess
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "create_experiment.py"
SPEC = importlib.util.spec_from_file_location("pithos_create_experiment", SCRIPT_PATH)
create_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(create_module)


def test_create_experiment_injects_active_ground_truth_and_git(tmp_path):
    source_harness = Path(__file__).parents[1]
    experiments = tmp_path / "experiments"

    target = create_module.create_experiment(source_harness, experiments, "audio-lab")
    configuration = json.loads((target / ".pithos.json").read_text(encoding="utf-8"))

    assert (target / "PROJECT.md").is_file()
    assert (target / "AGENTS.md").read_bytes() == (source_harness / "ground_truth" / "AGENTS.md").read_bytes()
    assert (target / ".pi" / "skills" / "pithos-continuity" / "SKILL.md").is_file()
    assert configuration["experiment_id"] == "audio-lab"
    assert configuration["runtime"] == "docker"
    branch = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=target,
        check=True,
        capture_output=True,
        text=True,
    )
    assert branch.stdout.strip() == "main"


def test_create_experiment_refuses_invalid_or_existing_target(tmp_path):
    source_harness = Path(__file__).parents[1]
    experiments = tmp_path / "experiments"

    with pytest.raises(ValueError, match="lowercase slug"):
        create_module.create_experiment(source_harness, experiments, "Bad Name")

    create_module.create_experiment(source_harness, experiments, "valid-name")
    with pytest.raises(FileExistsError):
        create_module.create_experiment(source_harness, experiments, "valid-name")
