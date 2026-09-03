import importlib.util
import json
import subprocess
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


def test_docker_start_is_bounded(tmp_path, monkeypatch):
    workspace = _configured_workspace(tmp_path, "first-task")
    configuration_path = workspace / ".pithos.json"
    configuration = json.loads(configuration_path.read_text())
    configuration["runtime"] = "docker"
    configuration_path.write_text(json.dumps(configuration), encoding="utf-8")
    observed = []

    def run(command, **kwargs):
        observed.append((command, kwargs))

        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(run_module.subprocess, "run", run)

    with pytest.raises(subprocess.TimeoutExpired):
        run_module.launch(workspace, tmp_path / "logs")

    [(command, kwargs)] = observed
    assert command[:2] == ["docker", "compose"]
    assert kwargs["timeout"] == run_module.DOCKER_START_TIMEOUT_SECONDS


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


def test_completed_autonomous_rush_authors_and_launches_the_next_one(tmp_path, monkeypatch):
    workspace = _configured_workspace(tmp_path, "band-smoothing")
    configuration_path = workspace / ".pithos.json"
    configuration = json.loads(configuration_path.read_text())
    configuration["seed"] = "Construire un visualiseur audio destiné au VJing."
    configuration["model"] = "fake-model"
    configuration["target_files"] = ["src/audio_visualizer.py"]
    configuration_path.write_text(json.dumps(configuration), encoding="utf-8")
    logs_root = tmp_path / "logs"
    completion_path = logs_root / "runtime" / "audio-lab-completed.json"
    completion_path.parent.mkdir(parents=True)
    completion_path.write_text(
        json.dumps({"micro_rush_id": "band-smoothing", "mission_id": "run-old"}),
        encoding="utf-8",
    )

    class Author:
        def __init__(self, model, project, author_workspace):
            assert model == "fake-model"
            assert author_workspace == workspace

        def __call__(self, state):
            updated = dict(configuration)
            updated["micro_rush_id"] = "level-clamping"
            updated["title"] = "Borner les niveaux"
            updated["description"] = "Borner chaque niveau entre zéro et un."
            configuration_path.write_text(json.dumps(updated), encoding="utf-8")

            return True, "proposed next micro-rush 'level-clamping': Borner les niveaux"

    launched = []

    def launch_orchestrated(workspace_arg, logs, git, telegram):
        launched.append(json.loads((workspace_arg / ".pithos.json").read_text())["micro_rush_id"])

        return SimpleNamespace(status="completed", micro_rush_id="level-clamping", mission_id="run-new")

    monkeypatch.setattr(run_module, "NextRushAuthor", Author)
    monkeypatch.setattr(run_module, "launch_orchestrated", launch_orchestrated)
    monkeypatch.setattr(run_module, "_git_remote", lambda workspace_arg: None)

    result = run_module.launch(workspace, logs_root)

    assert result["status"] == "completed"
    assert launched == ["level-clamping"]
    completion = json.loads(completion_path.read_text())
    assert completion["micro_rush_id"] == "level-clamping"


def test_completed_autonomous_rush_retries_planning_on_a_later_wake(tmp_path, monkeypatch):
    workspace = _configured_workspace(tmp_path, "band-smoothing")
    configuration_path = workspace / ".pithos.json"
    configuration = json.loads(configuration_path.read_text())
    configuration["seed"] = "Construire un visualiseur audio destiné au VJing."
    configuration["model"] = "fake-model"
    configuration_path.write_text(json.dumps(configuration), encoding="utf-8")
    logs_root = tmp_path / "logs"
    completion_path = logs_root / "runtime" / "audio-lab-completed.json"
    completion_path.parent.mkdir(parents=True)
    completion_path.write_text(
        json.dumps({"micro_rush_id": "band-smoothing", "mission_id": "run-old"}),
        encoding="utf-8",
    )

    class Author:
        def __init__(self, *args):
            pass

        def __call__(self, state):
            return False, "propose_next_rush failed: model unreachable"

    monkeypatch.setattr(run_module, "NextRushAuthor", Author)
    monkeypatch.setattr(
        run_module,
        "launch_orchestrated",
        lambda *args: pytest.fail("a failed handoff must not relaunch the completed rush"),
    )

    first = run_module.launch(workspace, logs_root)
    second = run_module.launch(workspace, logs_root)

    assert first["status"] == "planning_failed"
    assert second["status"] == "planning_failed"
    assert first["micro_rush_id"] == "band-smoothing"


def test_completed_project_proposes_stop_once_without_launching_a_mission(tmp_path, monkeypatch):
    workspace = _configured_workspace(tmp_path, "final-rush")
    configuration_path = workspace / ".pithos.json"
    configuration = json.loads(configuration_path.read_text())
    configuration["seed"] = "Construire un visualiseur audio destiné au VJing."
    configuration["model"] = "fake-model"
    configuration["regression_command"] = ["python", "-c", "raise SystemExit(0)"]
    configuration_path.write_text(json.dumps(configuration), encoding="utf-8")
    docs = workspace / "docs"
    docs.mkdir()
    (docs / "ROADMAP.md").write_text("- [DONE] Produit livré.\n", encoding="utf-8")
    logs_root = tmp_path / "logs"
    launched = []

    def launch_orchestrated(*_args):
        launched.append(True)

        return SimpleNamespace(status="completed", micro_rush_id="final-rush", mission_id="run-new")

    monkeypatch.setattr(run_module, "launch_orchestrated", launch_orchestrated)

    first = run_module.launch(workspace, logs_root)
    second = run_module.launch(workspace, logs_root)

    assert first["status"] == "stop_proposed"
    assert first["notification"] == "not configured"
    assert second["status"] == "skipped"
    marker = json.loads(
        (logs_root / "runtime" / "audio-lab-stop-proposal.json").read_text()
    )
    assert marker["run_id"] == first["run_id"]
    assert marker["roadmap_sha256"]
    assert launched == []

    (docs / "ROADMAP.md").write_text("- [TODO] Nouveau travail.\n", encoding="utf-8")
    third = run_module.launch(workspace, logs_root)

    assert third["status"] == "completed"
    assert launched == [True]


def test_newly_completed_project_publishes_stop_for_the_updated_roadmap(tmp_path, monkeypatch):
    workspace = _configured_workspace(tmp_path, "final-rush")
    configuration_path = workspace / ".pithos.json"
    configuration = json.loads(configuration_path.read_text())
    configuration["seed"] = "Construire un visualiseur audio destiné au VJing."
    configuration_path.write_text(json.dumps(configuration), encoding="utf-8")
    roadmap_path = workspace / "docs" / "ROADMAP.md"
    roadmap_path.parent.mkdir()
    roadmap_path.write_text("- [TODO] Terminer le produit.\n", encoding="utf-8")

    def complete_project(*_args):
        roadmap_path.write_text("- [DONE] Terminer le produit.\n", encoding="utf-8")

        return SimpleNamespace(
            status="completed",
            micro_rush_id="final-rush",
            mission_id="run-final",
            artifacts={"stop_proposal": "all declared roadmap items are done"},
        )

    monkeypatch.setattr(run_module, "launch_orchestrated", complete_project)
    monkeypatch.setattr(run_module, "_git_remote", lambda _workspace: None)

    result = run_module.launch(workspace, tmp_path / "logs")

    marker_path = tmp_path / "logs" / "runtime" / "audio-lab-stop-proposal.json"
    marker = json.loads(marker_path.read_text())
    expected_hash = run_module.hashlib.sha256(roadmap_path.read_bytes()).hexdigest()
    assert result["status"] == "completed"
    assert result["stop_proposal"]["status"] == "stop_proposed"
    assert marker["roadmap_sha256"] == expected_hash


def test_reconciles_stale_mission_with_append_only_terminal_event(tmp_path):
    logs_root = tmp_path / "logs"
    mission_id = "run-20260824T180000Z-a1b2c3"
    mission_root = logs_root / "missions" / mission_id
    mission_root.mkdir(parents=True)
    state_path = mission_root / "state.json"
    state_path.write_text(
        json.dumps(
            {
                "mission_id": mission_id,
                "experiment_id": "audio-lab",
                "phase": "test",
                "status": "running",
                "failure_summary": "oracle failed",
                "history": [],
            }
        ),
        encoding="utf-8",
    )

    recovered = run_module._reconcile_stale_runs(logs_root, "audio-lab")

    state = json.loads(state_path.read_text())
    events = [json.loads(line) for line in (mission_root / "events.jsonl").read_text().splitlines()]
    assert recovered == [mission_id]
    assert state["phase"] == "interrupted"
    assert state["status"] == "interrupted"
    assert "oracle failed" in state["failure_summary"]
    assert events[-1]["type"] == "run.finished"
    assert events[-1]["payload"]["status"] == "interrupted"


def test_reconciles_stale_generic_run_document(tmp_path):
    logs_root = tmp_path / "logs"
    run_id = "run-20260824T180000Z-a1b2c3"
    run_root = logs_root / "runs" / run_id
    run_root.mkdir(parents=True)
    run_path = run_root / "run.json"
    run_path.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "experiment_id": "audio-lab",
                "status": "running",
                "finished_at": None,
                "stop_reason": None,
                "success": {"process": None, "protocol": None, "task": None, "report": None},
            }
        ),
        encoding="utf-8",
    )

    recovered = run_module._reconcile_stale_runs(logs_root, "audio-lab")

    run = json.loads(run_path.read_text())
    events = [json.loads(line) for line in (run_root / "events.jsonl").read_text().splitlines()]
    assert recovered == [run_id]
    assert run["status"] == "interrupted"
    assert run["finished_at"]
    assert run["success"]["process"] is False
    assert events[-1]["payload"]["status"] == "interrupted"


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


def test_autonomous_rush_at_failure_cap_is_replanned_without_human_intervention(tmp_path, monkeypatch):
    workspace = _configured_workspace(tmp_path, "frame-pipeline-v2")
    configuration_path = workspace / ".pithos.json"
    configuration = json.loads(configuration_path.read_text())
    configuration["seed"] = "Construire un visualiseur audio destiné au VJing."
    configuration["model"] = "fake-model"
    configuration_path.write_text(json.dumps(configuration), encoding="utf-8")
    logs_root = tmp_path / "logs"
    failure_path = logs_root / "runtime" / "audio-lab-failures.json"
    failure_path.parent.mkdir(parents=True)
    failure_path.write_text(
        json.dumps({"micro_rush_id": "frame-pipeline-v2", "count": run_module.MAX_CONSECUTIVE_FAILURES}),
        encoding="utf-8",
    )

    class Author:
        def __init__(self, *args):
            pass

        def __call__(self, state):
            updated = dict(configuration)
            updated["micro_rush_id"] = "different-rush"
            updated["title"] = "Choisir une autre amélioration"
            updated["description"] = "Améliorer un autre comportement borné."
            configuration_path.write_text(json.dumps(updated), encoding="utf-8")

            return True, "proposed next micro-rush 'different-rush'"

    monkeypatch.setattr(run_module, "NextRushAuthor", Author)
    monkeypatch.setattr(run_module, "_git_remote", lambda workspace_arg: None)
    monkeypatch.setattr(
        run_module,
        "launch_orchestrated",
        lambda *args: SimpleNamespace(status="completed", micro_rush_id="different-rush", mission_id="run-new"),
    )

    result = run_module.launch(workspace, logs_root)

    assert result["status"] == "completed"
    completion_path = logs_root / "runtime" / "audio-lab-completed.json"
    completion = json.loads(completion_path.read_text())
    assert completion["micro_rush_id"] == "different-rush"


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
