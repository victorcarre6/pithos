import io
import json

import pytest

from pithos_orchestrator.plan_todo import TodoPlanner
from pithos_orchestrator.state import MissionState


def _opener_yielding(payload):
    def opener(request, timeout):
        body = {"response": json.dumps(payload)}

        return io.BytesIO(json.dumps(body).encode())

    return opener


def _project(**overrides):
    project = {
        "schema_version": 1,
        "experiment_id": "visualizer-dry-run",
        "title": "Borner les niveaux lissés",
        "description": "Ajouter une fonction qui borne chaque niveau de bande entre 0 et 1.",
        "target_files": ["src/audio_visualizer.py"],
    }
    project.update(overrides)

    return project


def _write_module(workspace, body):
    module = workspace / "src" / "audio_visualizer.py"
    module.parent.mkdir(parents=True, exist_ok=True)
    module.write_text(body, encoding="utf-8")


def test_valid_plan_populates_state_todo(tmp_path):
    _write_module(tmp_path, "def split_bands(x):\n    pass\n\n\ndef smooth_levels(a, b):\n    pass\n")
    project = _project()
    payload = {
        "items": [
            {
                "title": "Clamper smooth_levels",
                "description": "Borner la sortie de smooth_levels dans [0, 1].",
                "target_files": ["src/audio_visualizer.py"],
            }
        ]
    }
    planner = TodoPlanner("fake-model", project, tmp_path, opener=_opener_yielding(payload))
    state = MissionState("run-1", "visualizer-dry-run")

    success, reason = planner(state)

    assert success is True
    assert "1 item(s)" in reason
    assert state.todo == [
        {
            "title": "Clamper smooth_levels",
            "description": "Borner la sortie de smooth_levels dans [0, 1].",
            "target_files": ["src/audio_visualizer.py"],
            "status": "pending",
        }
    ]
    assert state.todo_index == 0


def test_plan_facts_include_existing_functions(tmp_path):
    _write_module(tmp_path, "def split_bands(x):\n    pass\n\n\ndef smooth_levels(a, b):\n    pass\n")
    project = _project()
    payload = {"items": [{"title": "T", "description": "D", "target_files": ["src/audio_visualizer.py"]}]}
    captured = []

    def opener(request, timeout):
        captured.append(json.loads(request.data)["prompt"])
        body = {"response": json.dumps(payload)}

        return io.BytesIO(json.dumps(body).encode())

    planner = TodoPlanner("fake-model", project, tmp_path, opener=opener)

    planner(MissionState("run-1", "visualizer-dry-run"))

    [prompt] = captured
    assert '"existing_functions": ["smooth_levels", "split_bands"]' in prompt


def test_a_target_file_outside_the_rush_leaves_state_todo_empty(tmp_path):
    _write_module(tmp_path, "def smooth_levels(a, b):\n    pass\n")
    project = _project()
    payload = {
        "items": [
            {"title": "T", "description": "D", "target_files": ["src/other_module.py"]},
        ]
    }
    planner = TodoPlanner("fake-model", project, tmp_path, opener=_opener_yielding(payload))
    state = MissionState("run-1", "visualizer-dry-run")

    success, reason = planner(state)

    assert success is False
    assert "not one of the rush's approved target files" in reason
    assert state.todo == []


def test_an_oversize_item_count_leaves_state_todo_empty(tmp_path):
    _write_module(tmp_path, "def smooth_levels(a, b):\n    pass\n")
    project = _project()
    payload = {"items": [{"title": f"T{i}", "description": "D", "target_files": ["src/audio_visualizer.py"]} for i in range(5)]}
    planner = TodoPlanner("fake-model", project, tmp_path, opener=_opener_yielding(payload))
    state = MissionState("run-1", "visualizer-dry-run")

    success, reason = planner(state)

    assert success is False
    assert state.todo == []


def test_an_unreachable_model_leaves_state_todo_empty_for_a_graceful_fallback(tmp_path):
    project = _project()

    def unreachable(request, timeout):
        raise OSError("connection refused")

    planner = TodoPlanner("fake-model", project, tmp_path, opener=unreachable)
    state = MissionState("run-1", "visualizer-dry-run")

    success, reason = planner(state)

    assert success is False
    assert "proceeding with a single implicit item" in reason
    assert state.todo == []


@pytest.mark.parametrize("path", ["/etc/passwd", "../outside.py"])
def test_a_path_outside_the_workspace_leaves_state_todo_empty(tmp_path, path):
    project = _project()
    payload = {"items": [{"title": "T", "description": "D", "target_files": [path]}]}
    planner = TodoPlanner("fake-model", project, tmp_path, opener=_opener_yielding(payload))
    state = MissionState("run-1", "visualizer-dry-run")

    success, reason = planner(state)

    assert success is False
    assert state.todo == []
