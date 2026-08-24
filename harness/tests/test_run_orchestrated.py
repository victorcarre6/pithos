import json
import time

from pithos_orchestrator import launcher as run_module
from pithos_orchestrator.state import MissionState


def test_lifecycle_notifications_are_static_and_best_effort(tmp_path, monkeypatch):
    requests = []
    monkeypatch.setattr(run_module, "send_request", lambda socket, request: requests.append(request))
    state = MissionState("run-20260824T142000Z-a1b2c3", "visualizer")

    run_module._notify(tmp_path / "telegram.sock", state, "started")
    state.status = "completed"
    run_module._notify(tmp_path / "telegram.sock", state, "finished")

    assert [request["kind"] for request in requests] == ["INFO", "INFO"]
    assert [request["request_id"].rsplit("-", 1)[-1] for request in requests] == ["started", "finished"]


def test_failed_lifecycle_notification_is_warning_and_never_raises(tmp_path, monkeypatch):
    state = MissionState("run-20260824T142100Z-a1b2c3", "visualizer", status="failed")
    requests = []
    monkeypatch.setattr(run_module, "send_request", lambda socket, request: requests.append(request))

    run_module._notify(tmp_path / "telegram.sock", state, "finished")

    assert requests[0]["kind"] == "WARNING"

    def unavailable(socket, request):
        raise OSError("offline")

    monkeypatch.setattr(run_module, "send_request", unavailable)
    run_module._notify(tmp_path / "telegram.sock", state, "finished")


def test_launch_writes_observable_mission_lifecycle(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    config = tmp_path / "pi-config"
    config.mkdir()
    project = {
        "experiment_id": "observable",
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
