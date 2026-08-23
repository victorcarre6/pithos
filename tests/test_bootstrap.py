import importlib.util
import json
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "bootstrap.py"
SPEC = importlib.util.spec_from_file_location("pithos_bootstrap", SCRIPT_PATH)
bootstrap_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bootstrap_module)


def _project(tmp_path):
    project_root = tmp_path / "project"
    source_root = Path(__file__).parents[1]

    for relative_path in bootstrap_module.REQUIRED_PROJECT_FILES:
        target = project_root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        source = source_root / relative_path
        target.write_bytes(source.read_bytes())

    return project_root


def test_bootstrap_is_idempotent_and_preserves_live_log(tmp_path, monkeypatch):
    project_root = _project(tmp_path)
    logs_root = tmp_path / "logs"
    monkeypatch.setattr(bootstrap_module.shutil, "which", lambda command: f"/bin/{command}")

    first = bootstrap_module.bootstrap(project_root, logs_root)
    (logs_root / "live.log").write_text("existing event\n", encoding="utf-8")
    second = bootstrap_module.bootstrap(project_root, logs_root)

    assert first["ready"] is True
    assert second["ready"] is True
    assert (logs_root / "live.log").read_text(encoding="utf-8") == "existing event\n"
    assert (project_root / "experiments").is_dir()
    assert (project_root / "journals" / "harness").is_dir()


def test_bootstrap_refuses_missing_controlled_file_before_writing(tmp_path, monkeypatch):
    project_root = _project(tmp_path)
    logs_root = tmp_path / "logs"
    (project_root / "ground_truth" / "AGENTS.md").unlink()
    monkeypatch.setattr(bootstrap_module.shutil, "which", lambda command: f"/bin/{command}")

    with pytest.raises(RuntimeError, match="ground_truth/AGENTS.md"):
        bootstrap_module.bootstrap(project_root, logs_root)

    assert not logs_root.exists()


def test_bootstrap_rejects_invalid_configuration(tmp_path, monkeypatch):
    project_root = _project(tmp_path)
    logs_root = tmp_path / "logs"
    settings = project_root / "config" / "pi" / "settings.json"
    settings.write_text("not json", encoding="utf-8")
    monkeypatch.setattr(bootstrap_module.shutil, "which", lambda command: f"/bin/{command}")

    with pytest.raises(json.JSONDecodeError):
        bootstrap_module.bootstrap(project_root, logs_root)

    assert not logs_root.exists()
