import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace


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
        lambda workspace, logs, git, telegram: SimpleNamespace(status="completed"),
    )

    result = run_module.launch(workspace, tmp_path / "logs")

    assert result == {"status": "completed"}
    assert not any(command[:2] == ["docker", "compose"] for command in commands)


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
