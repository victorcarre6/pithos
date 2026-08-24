import json
import io
import time
from pathlib import Path

import pytest

from pithos_orchestrator import launcher as run_module
from pithos_orchestrator.recap import generate_recap
from pithos_orchestrator.state import MissionState
from pithos_runner.events import EventWriter


def test_lifecycle_notifications_are_static_and_best_effort(tmp_path, monkeypatch):
    requests = []
    monkeypatch.setattr(run_module, "send_request", lambda socket, request: requests.append(request))
    state = MissionState("run-20260824T142000Z-a1b2c3", "visualizer")
    project = {
        "title": "Lissage audio",
        "description": "Lisser les trois bandes FFT.",
    }

    run_module._notify(tmp_path / "telegram.sock", project, state, "started")
    state.status = "completed"
    run_module._notify(
        tmp_path / "telegram.sock",
        project,
        state,
        "finished",
        {"duration_ms": 12_500},
    )

    assert [request["kind"] for request in requests] == ["INFO", "INFO"]
    assert [request["request_id"].rsplit("-", 1)[-1] for request in requests] == ["started", "finished"]
    assert "Lissage audio" in requests[0]["text"]
    assert "Lisser les trois bandes FFT." in requests[0]["text"]
    assert "13 s" in requests[1]["text"]


def test_failed_lifecycle_notification_is_warning_and_never_raises(tmp_path, monkeypatch):
    state = MissionState(
        "run-20260824T142100Z-a1b2c3",
        "visualizer",
        status="failed",
        failure_summary="oracle failed\ninternal details",
    )
    project = {"title": "Lissage audio", "description": "Lisser les bandes."}
    requests = []
    monkeypatch.setattr(run_module, "send_request", lambda socket, request: requests.append(request))

    run_module._notify(tmp_path / "telegram.sock", project, state, "finished")

    assert requests[0]["kind"] == "WARNING"
    assert "Cause : oracle failed" in requests[0]["text"]

    def unavailable(socket, request):
        raise OSError("offline")

    monkeypatch.setattr(run_module, "send_request", unavailable)
    run_module._notify(tmp_path / "telegram.sock", project, state, "finished")


def test_recap_generation_is_bounded_factual_and_persisted(tmp_path):
    captured = {}

    def open_request(request, timeout):
        captured["payload"] = json.loads(request.data)
        captured["timeout"] = timeout
        response = {
            "response": json.dumps(
                {
                    "opening": "J-j-je vais pas mentir, euh...",
                    "reaction": "Oh, punaise... ça a un peu résisté.",
                    "closing": "Enfin... voilà, quoi.",
                }
            )
        }

        return io.BytesIO(json.dumps(response).encode())

    artifact = tmp_path / "telegram-recap.txt"
    text = generate_recap(
        "pithos/ling",
            {
                "goal": "Lisser trois bandes",
                "status": "completed",
                "validation": "PASS",
            "changed_files": ["src/audio.py"],
            "repairs": 1,
            "tool_calls": 2,
            "tool_failures": 1,
            "duration_seconds": 8,
        },
        artifact,
        opener=open_request,
    )

    prompt = captured["payload"]["prompt"]
    assert text.startswith("J-j-je")
    assert "J'ai modifié src/audio.py" in text
    assert "validation externe est PASS" in text
    assert artifact.read_text().strip() == text
    assert captured["timeout"] == 45
    assert captured["payload"]["options"]["num_predict"] == 100
    assert captured["payload"]["think"] is False
    assert captured["payload"]["format"]["required"] == ["opening", "reaction", "closing"]
    assert '"validation": "PASS"' in prompt


def test_generated_recap_is_sent_once_from_terminal_facts(tmp_path, monkeypatch):
    requests = []
    state = MissionState(
        "run-20260824T142200Z-a1b2c3",
        "visualizer",
        status="completed",
        repair_attempts=2,
        changed_files=["src/audio.py"],
        artifacts={"pull_request": "https://example.test/pr/4"},
    )
    project = {"title": "Lissage audio", "description": "Lisser les bandes."}
    events_path = tmp_path / "events.jsonl"
    events = EventWriter(events_path, state.mission_id)

    def generate(model, facts, artifact_path):
        Path(artifact_path).write_text("Oh, mince... ça passe enfin.\n")
        assert facts["validation"] == "PASS"
        assert facts["repairs"] == 2

        return "Oh, mince... ça passe enfin."

    monkeypatch.setattr(run_module, "generate_recap", generate)
    monkeypatch.setattr(run_module, "send_request", lambda socket, request: requests.append(request))

    run_module._send_recap(
        tmp_path / "telegram.sock",
        project,
        state,
        {"duration_ms": 8_000, "tool_calls": 3, "tool_failures": 1},
        "pithos/ling",
        tmp_path,
        events,
    )

    generated = json.loads(events_path.read_text())
    assert requests[0]["request_id"].endswith("-orchestrated-recap")
    assert requests[0]["text"] == "Oh, mince... ça passe enfin."
    assert generated["type"] == "telegram.recap_generated"
    assert generated["payload"]["characters"] == 28


def test_recap_failure_is_journaled_without_sending(tmp_path, monkeypatch):
    requests = []
    state = MissionState("run-20260824T142300Z-a1b2c3", "visualizer", status="completed")
    project = {"title": "Lissage audio", "description": "Lisser les bandes."}
    events_path = tmp_path / "events.jsonl"
    events = EventWriter(events_path, state.mission_id)

    def fail(*args):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(run_module, "generate_recap", fail)
    monkeypatch.setattr(run_module, "send_request", lambda socket, request: requests.append(request))

    run_module._send_recap(
        tmp_path / "telegram.sock",
        project,
        state,
        {"duration_ms": 1_000},
        "pithos/ling",
        tmp_path,
        events,
    )

    event = json.loads(events_path.read_text())
    assert event["type"] == "telegram.recap_failed"
    assert requests == []
    assert state.status == "completed"


def test_launch_requires_human_readable_telegram_metadata(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    project = {
        "experiment_id": "observable",
        "description": "Vérifier le cycle de vie.",
        "validation_command": ["python", "acceptance.py"],
    }
    (workspace / ".pithos.json").write_text(json.dumps(project))

    with pytest.raises(ValueError, match="non-empty title"):
        run_module.launch(workspace, tmp_path / "logs")


def test_launch_writes_observable_mission_lifecycle(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    config = tmp_path / "pi-config"
    config.mkdir()
    project = {
        "experiment_id": "observable",
        "title": "Mission observable",
        "description": "Vérifier le cycle de vie.",
        "runtime": "host",
        "model": "pithos/ling",
        "pi_config": str(config),
        "validation_command": ["python", "acceptance.py"],
    }
    (workspace / ".pithos.json").write_text(json.dumps(project))

    def complete(orchestrator, state, context_factory):
        state.status = "completed"
        state.phase = "done"

        return state

    monkeypatch.setattr(run_module.Orchestrator, "run", complete)

    result = run_module.launch(workspace, tmp_path / "logs")

    events_path = next((tmp_path / "logs" / "missions").glob("*/events.jsonl"))
    events = [json.loads(line) for line in events_path.read_text().splitlines()]
    assert result.status == "completed"
    assert [event["type"] for event in events] == ["run.started", "run.finished"]
    assert events[0]["payload"]["model"] == "pithos/ling"
    assert events[1]["payload"]["status"] == "completed"


def test_launch_requires_target_files_when_validation_command_is_absent(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    project = {
        "experiment_id": "observable",
        "title": "Sans oracle",
        "description": "Aucun fichier cible fourni.",
    }
    (workspace / ".pithos.json").write_text(json.dumps(project))

    with pytest.raises(ValueError, match="target_files to auto-author"):
        run_module.launch(workspace, tmp_path / "logs")


def test_launch_without_validation_command_starts_at_author_oracle(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    config = tmp_path / "pi-config"
    config.mkdir()
    project = {
        "experiment_id": "observable",
        "title": "Contrat généré",
        "description": "Le harnais génère l'oracle depuis la description.",
        "runtime": "host",
        "model": "pithos/ling",
        "pi_config": str(config),
        "target_files": ["src/module.py"],
    }
    (workspace / ".pithos.json").write_text(json.dumps(project))

    seen_phase = {}

    def complete(orchestrator, state, context_factory):
        seen_phase["initial"] = state.phase
        assert orchestrator.oracle_author is not None
        state.status = "completed"
        state.phase = "done"

        return state

    monkeypatch.setattr(run_module.Orchestrator, "run", complete)

    result = run_module.launch(workspace, tmp_path / "logs")

    events_path = next((tmp_path / "logs" / "missions").glob("*/events.jsonl"))
    events = [json.loads(line) for line in events_path.read_text().splitlines()]
    assert seen_phase["initial"] == "author_oracle"
    assert result.status == "completed"
    assert events[0]["payload"]["oracle"] == "generated"


def test_finish_payload_aggregates_all_phase_metrics(tmp_path):
    phases = tmp_path / "phases"
    for number, total_tokens in enumerate((13, 21), start=1):
        phase = phases / f"0{number}-implement"
        phase.mkdir(parents=True)
        result = {
            "metrics": {
                "input_tokens": total_tokens - 3,
                "output_tokens": 3,
                "total_tokens": total_tokens,
                "tool_calls": number,
                "tool_failures": number - 1,
            }
        }
        (phase / "result.json").write_text(json.dumps(result))
    state = MissionState("run-20260824T160000Z-a1b2c3", "observable", status="completed")

    payload = run_module._finish_payload(state, tmp_path, time.monotonic())

    assert payload["total_tokens"] == 34
    assert payload["tool_calls"] == 3
    assert payload["tool_failures"] == 1
    assert payload["duration_ms"] >= 0
