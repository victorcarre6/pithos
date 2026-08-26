import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from pithos_runner.lock import LockHeld, RunLock


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "run_experiment.py"
SPEC = importlib.util.spec_from_file_location("pithos_run_experiment", SCRIPT_PATH)
run_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(run_module)


def test_host_launch_does_not_start_docker(tmp_path, monkeypatch):
    repository = tmp_path / "repository"
    workspace = repository / "experiments" / "audio-lab"
    workspace.mkdir(parents=True)
    harness = repository / "harness"
    configuration = {
        "schema_version": 1,
        "experiment_id": "audio-lab",
        "micro_rush_id": "first-task",
        "runtime": "host",
        "pi_config": str(harness / "config" / "pi-host"),
        "ground_truth": str(harness / "ground_truth"),
    }
    (workspace / ".pithos.json").write_text(json.dumps(configuration), encoding="utf-8")

    commands = []

    def run(command, **kwargs):
        commands.append(command)

        return SimpleNamespace(returncode=1, stdout="")

    class Process:
        def terminate(self):
            pass

        def wait(self, timeout):
            pass

    monkeypatch.setattr(run_module.subprocess, "run", run)
    monkeypatch.setattr(run_module, "_start_broker", lambda *args: Process())
    monkeypatch.setattr(
        run_module,
        "launch_orchestrated",
        lambda workspace, logs, git, telegram: SimpleNamespace(
            status="completed",
            micro_rush_id="first-task",
            mission_id="run-20260824T180000Z-a1b2c3",
        ),
    )

    result = run_module.launch(workspace, tmp_path / "logs")

    assert result["status"] == "completed"
    assert not any(command[:2] == ["docker", "compose"] for command in commands)
    completion = json.loads(
        (tmp_path / "logs" / "runtime" / "audio-lab-completed.json").read_text()
    )
    assert completion["micro_rush_id"] == "first-task"


def test_environment_loads_only_telegram_values_without_overriding_host(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEGRAM_USER_ID", "host-user")
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    (tmp_path / ".env").write_text(
        "TELEGRAM_BOT_TOKEN='file-token'\n"
        "TELEGRAM_USER_ID=file-user\n"
        "UNRELATED_SECRET=ignored\n",
        encoding="utf-8",
    )

    environment = run_module._environment_for(tmp_path, tmp_path / "logs")

    assert environment["TELEGRAM_BOT_TOKEN"] == "file-token"
    assert environment["TELEGRAM_USER_ID"] == "host-user"
    assert "UNRELATED_SECRET" not in environment


def test_launch_refuses_overlapping_experiment(tmp_path):
    repository = tmp_path / "repository"
    workspace = repository / "experiments" / "audio-lab"
    workspace.mkdir(parents=True)
    harness = repository / "harness"
    configuration = {
        "schema_version": 1,
        "experiment_id": "audio-lab",
        "runtime": "host",
        "pi_config": str(harness / "config" / "pi-host"),
        "ground_truth": str(harness / "ground_truth"),
    }
    (workspace / ".pithos.json").write_text(json.dumps(configuration), encoding="utf-8")
    logs_root = tmp_path / "logs"

    with RunLock(logs_root / "runtime" / "audio-lab.lock"):
        with pytest.raises(LockHeld, match="live PID"):
            run_module.launch(workspace, logs_root)


def test_completed_micro_rush_is_skipped_until_identity_changes(tmp_path, monkeypatch):
    repository = tmp_path / "repository"
    workspace = repository / "experiments" / "audio-lab"
    workspace.mkdir(parents=True)
    harness = repository / "harness"
    configuration = {
        "schema_version": 1,
        "experiment_id": "audio-lab",
        "micro_rush_id": "band-smoothing",
        "runtime": "host",
        "pi_config": str(harness / "config" / "pi-host"),
        "ground_truth": str(harness / "ground_truth"),
    }
    (workspace / ".pithos.json").write_text(json.dumps(configuration), encoding="utf-8")
    logs_root = tmp_path / "logs"
    completion_path = logs_root / "runtime" / "audio-lab-completed.json"
    completion_path.parent.mkdir(parents=True)
    completion_path.write_text(
        json.dumps(
            {
                "micro_rush_id": "band-smoothing",
                "mission_id": "run-20260824T180000Z-a1b2c3",
            }
        )
    )
    monkeypatch.setattr(
        run_module,
        "launch_orchestrated",
        lambda *args: pytest.fail("completed task must not launch"),
    )

    result = run_module.launch(workspace, logs_root)

    assert result["status"] == "skipped"
    assert result["micro_rush_id"] == "band-smoothing"


def _configured_workspace(tmp_path, micro_rush_id):
    repository = tmp_path / "repository"
    workspace = repository / "experiments" / "audio-lab"
    workspace.mkdir(parents=True)
    harness = repository / "harness"
    configuration = {
        "schema_version": 1,
        "experiment_id": "audio-lab",
        "micro_rush_id": micro_rush_id,
        "runtime": "host",
        "pi_config": str(harness / "config" / "pi-host"),
        "ground_truth": str(harness / "ground_truth"),
    }
    (workspace / ".pithos.json").write_text(json.dumps(configuration), encoding="utf-8")

    return workspace


def test_micro_rush_failing_repeatedly_is_skipped_after_max_consecutive_failures(tmp_path, monkeypatch):
    workspace = _configured_workspace(tmp_path, "frame-pipeline-v2")
    logs_root = tmp_path / "logs"
    monkeypatch.setattr(
        run_module,
        "launch_orchestrated",
        lambda *args: SimpleNamespace(status="failed", micro_rush_id="frame-pipeline-v2", mission_id="run-x"),
    )

    for _ in range(run_module.MAX_CONSECUTIVE_FAILURES):
        result = run_module.launch(workspace, logs_root)
        assert result["status"] == "failed"

    monkeypatch.setattr(
        run_module,
        "launch_orchestrated",
        lambda *args: pytest.fail("a micro-rush stuck at the failure cap must not launch again"),
    )

    result = run_module.launch(workspace, logs_root)

    assert result["status"] == "skipped"
    assert result["consecutive_failures"] == run_module.MAX_CONSECUTIVE_FAILURES


def test_completed_run_clears_a_prior_failure_streak(tmp_path, monkeypatch):
    workspace = _configured_workspace(tmp_path, "frame-pipeline-v2")
    logs_root = tmp_path / "logs"
    failure_path = logs_root / "runtime" / "audio-lab-failures.json"
    failure_path.parent.mkdir(parents=True)
    failure_path.write_text(
        json.dumps({"micro_rush_id": "frame-pipeline-v2", "count": run_module.MAX_CONSECUTIVE_FAILURES - 1})
    )
    monkeypatch.setattr(
        run_module,
        "launch_orchestrated",
        lambda *args: SimpleNamespace(status="completed", micro_rush_id="frame-pipeline-v2", mission_id="run-x"),
    )

    result = run_module.launch(workspace, logs_root)

    assert result["status"] == "completed"
    assert not failure_path.is_file()
