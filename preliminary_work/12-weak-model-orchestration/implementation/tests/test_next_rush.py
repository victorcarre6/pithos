import io
import json

import pytest

from pithos_orchestrator.next_rush import NextRushAuthor, NextRushSpecError, _validate_proposal
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
        "title": "Lisser les bandes",
        "description": "Lisser les trois bandes FFT.",
        "micro_rush_id": "band-smoothing",
        "seed": "Construire un visualiseur audio destiné au VJing.",
        "runtime": "docker",
        "model": "pithos/ling-3.0-tiny:8b-16k",
        "target_files": ["src/audio_visualizer.py"],
        "validation_command": ["python", "acceptance.py"],
        "pi_config": "/config",
        "ground_truth": "/ground_truth",
    }
    project.update(overrides)

    return project


def test_valid_proposal_overwrites_pithos_json_and_preserves_infra_fields(tmp_path):
    project = _project()
    payload = {
        "micro_rush_id": "audio-source",
        "title": "Lire la source audio",
        "description": "Identifier la source de sortie audio active.",
        "target_files": ["src/audio_source.py"],
    }
    author = NextRushAuthor("fake-model", project, tmp_path, opener=_opener_yielding(payload))

    success, reason = author(state=MissionState("run-1", "visualizer-dry-run", changed_files=["src/audio_visualizer.py"]))

    assert success is True
    assert "audio-source" in reason
    written = json.loads((tmp_path / ".pithos.json").read_text(encoding="utf-8"))
    assert written["micro_rush_id"] == "audio-source"
    assert written["title"] == "Lire la source audio"
    assert written["target_files"] == ["src/audio_source.py"]
    assert "validation_command" not in written
    # infrastructure and long-term fields are copied verbatim, never model-authored
    assert written["seed"] == project["seed"]
    assert written["experiment_id"] == project["experiment_id"]
    assert written["pi_config"] == project["pi_config"]
    assert written["ground_truth"] == project["ground_truth"]
    assert written["runtime"] == project["runtime"]
    assert written["model"] == project["model"]


def test_skips_without_touching_the_workspace_when_no_seed_is_configured(tmp_path):
    project = _project(seed="")
    calls = []

    def opener(request, timeout):
        calls.append(request)
        raise AssertionError("should never call the model without a seed")

    author = NextRushAuthor("fake-model", project, tmp_path, opener=opener)

    success, reason = author(state=MissionState("run-1", "visualizer-dry-run"))

    assert success is False
    assert "no seed configured" in reason
    assert not calls
    assert not (tmp_path / ".pithos.json").is_file()


def test_rejects_a_proposal_reusing_the_current_micro_rush_id(tmp_path):
    project = _project()
    payload = {
        "micro_rush_id": "band-smoothing",
        "title": "Encore la même chose",
        "description": "Répète le rush courant.",
        "target_files": ["src/audio_visualizer.py"],
    }
    author = NextRushAuthor("fake-model", project, tmp_path, opener=_opener_yielding(payload))

    success, reason = author(state=MissionState("run-1", "visualizer-dry-run"))

    assert success is False
    assert "must differ from the current one" in reason
    assert not (tmp_path / ".pithos.json").is_file()


def test_rejects_an_oversize_title(tmp_path):
    project = _project()
    payload = {
        "micro_rush_id": "audio-source",
        "title": "x" * 161,
        "description": "Description valide.",
        "target_files": ["src/audio_source.py"],
    }
    author = NextRushAuthor("fake-model", project, tmp_path, opener=_opener_yielding(payload))

    success, reason = author(state=MissionState("run-1", "visualizer-dry-run"))

    assert success is False
    assert "title" in reason


@pytest.mark.parametrize("path", ["/etc/passwd", "../outside.py", "src/../../outside.py"])
def test_rejects_target_files_that_escape_the_workspace(tmp_path, path):
    with pytest.raises(NextRushSpecError, match="escapes the workspace"):
        _validate_proposal(
            {
                "micro_rush_id": "audio-source",
                "title": "Titre",
                "description": "Description valide.",
                "target_files": [path],
            },
            "band-smoothing",
            tmp_path,
        )


@pytest.mark.parametrize("path", ["docs/api.md", "tests/fixture.json", "src/module.pyc"])
def test_rejects_a_non_python_target_file(tmp_path, path):
    with pytest.raises(NextRushSpecError, match="must be a Python file"):
        _validate_proposal(
            {
                "micro_rush_id": "audio-source",
                "title": "Titre",
                "description": "Description valide.",
                "target_files": [path],
            },
            "band-smoothing",
            tmp_path,
        )


def test_facts_list_functions_already_defined_in_the_changed_files(tmp_path):
    project = _project()
    changed = tmp_path / "src" / "audio_visualizer.py"
    changed.parent.mkdir(parents=True, exist_ok=True)
    changed.write_text("def split_bands(x):\n    pass\n\n\ndef smooth_levels(a, b):\n    pass\n", encoding="utf-8")
    payload = {
        "micro_rush_id": "level-clamping",
        "title": "Borner les niveaux",
        "description": "Clamper smooth_levels dans [0, 1].",
        "target_files": ["src/audio_visualizer.py"],
    }
    captured = []

    def opener(request, timeout):
        captured.append(json.loads(request.data)["prompt"])
        body = {"response": json.dumps(payload)}

        return io.BytesIO(json.dumps(body).encode())

    author = NextRushAuthor("fake-model", project, tmp_path, opener=opener)

    success, _ = author(state=MissionState("run-1", "visualizer-dry-run", changed_files=["src/audio_visualizer.py"]))

    assert success is True
    [prompt] = captured
    assert '"existing_functions": ["smooth_levels", "split_bands"]' in prompt


def test_facts_report_no_existing_functions_for_a_file_that_does_not_exist_yet(tmp_path):
    project = _project()
    payload = {
        "micro_rush_id": "audio-source",
        "title": "Lire la source audio",
        "description": "Identifier la source de sortie audio active.",
        "target_files": ["src/audio_source.py"],
    }
    captured = []

    def opener(request, timeout):
        captured.append(json.loads(request.data)["prompt"])
        body = {"response": json.dumps(payload)}

        return io.BytesIO(json.dumps(body).encode())

    author = NextRushAuthor("fake-model", project, tmp_path, opener=opener)

    author(state=MissionState("run-1", "visualizer-dry-run", changed_files=["src/does_not_exist.py"]))

    [prompt] = captured
    assert '"existing_functions": []' in prompt
