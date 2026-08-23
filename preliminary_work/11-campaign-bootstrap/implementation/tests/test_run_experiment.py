import importlib.util
import json
from pathlib import Path


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "run_experiment.py"
SPEC = importlib.util.spec_from_file_location("pithos_run_experiment", SCRIPT_PATH)
run_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(run_module)


def test_configuration_uses_generated_project_and_scoped_sockets(tmp_path):
    repository = tmp_path / "repository"
    workspace = repository / "experiments" / "audio-lab"
    workspace.mkdir(parents=True)
    harness = repository / "harness"
    configuration = {
        "schema_version": 1,
        "experiment_id": "audio-lab",
        "runtime": "docker",
        "pi_config": str(harness / "config" / "pi-docker"),
        "ground_truth": str(harness / "ground_truth"),
    }
    (workspace / ".pithos.json").write_text(json.dumps(configuration), encoding="utf-8")
    sockets = {
        "git": tmp_path / "git.sock",
        "harness": tmp_path / "harness.sock",
        "telegram": tmp_path / "telegram.sock",
    }

    runner = run_module.configuration_for(workspace, tmp_path / "logs", sockets)

    assert runner.experiment_id == "audio-lab"
    assert runner.workspace == workspace
    assert runner.runtime == "docker"
    assert runner.pi_config_dir == harness / "config" / "pi-docker"
    assert runner.harness_journals_root == repository / "journals" / "harness"
    assert runner.git_socket == sockets["git"]
