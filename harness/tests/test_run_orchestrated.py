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
