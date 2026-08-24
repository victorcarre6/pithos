import importlib.util
import json
import plistlib
from pathlib import Path
from types import SimpleNamespace

import pytest


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "install_launchd.py"
SPEC = importlib.util.spec_from_file_location("pithos_install_launchd", SCRIPT_PATH)
launchd = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(launchd)


def _workspace(tmp_path, experiment_id="audio-lab"):
    workspace = tmp_path / "experiments" / experiment_id
    workspace.mkdir(parents=True)
    project = {
        "schema_version": 1,
        "experiment_id": experiment_id,
    }
    (workspace / ".pithos.json").write_text(json.dumps(project), encoding="utf-8")

    return workspace


def test_definitions_use_canonical_launcher_without_secrets(tmp_path):
    harness = tmp_path / "harness"
    workspace = _workspace(tmp_path)
    logs = tmp_path / "logs"

    items = launchd.definitions(harness, workspace, logs, 10_800, tmp_path)

    runner = items["dev.pithos.runner.audio-lab"]
    collector = items["dev.pithos.events"]
    assert runner["StartInterval"] == 10_800
    assert runner["ProgramArguments"][1].endswith("scripts/run_experiment.py")
    assert runner["ProgramArguments"][2] == str(workspace.resolve())
    assert collector["KeepAlive"] is True
    assert collector["RunAtLoad"] is True
    assert "pithos_event_store.cli" in collector["ProgramArguments"]
    assert "TOKEN" not in json.dumps(items)


def test_write_and_install_private_plists(tmp_path, monkeypatch):
    harness = tmp_path / "harness"
    workspace = _workspace(tmp_path)
    items = launchd.definitions(harness, workspace, tmp_path / "logs", 10_800, tmp_path)
    agents = tmp_path / "LaunchAgents"
    commands = []

    def run(command, **kwargs):
        commands.append(command)

        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(launchd.subprocess, "run", run)

    paths = launchd.write_plists(items, agents)
    launchd.install(paths, 501)

    runner_path = paths["dev.pithos.runner.audio-lab"]
    with runner_path.open("rb") as plist_file:
        runner = plistlib.load(plist_file)
    assert runner["Label"] == "dev.pithos.runner.audio-lab"
    assert runner_path.stat().st_mode & 0o777 == 0o600
    assert ["launchctl", "bootstrap", "gui/501", str(runner_path)] in commands
    assert ["launchctl", "enable", "gui/501/dev.pithos.runner.audio-lab"] in commands


def test_invalid_experiment_id_is_rejected(tmp_path):
    workspace = _workspace(tmp_path, "Invalid ID")

    with pytest.raises(ValueError, match="not safe"):
        launchd.definitions(tmp_path / "harness", workspace, tmp_path / "logs", 10_800, tmp_path)
