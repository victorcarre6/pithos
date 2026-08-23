from pithos_model_probe.client import ProbeResponse
from pithos_model_probe.probe import probe_structured_output, probe_text, probe_tool_call, run_probe


class StubClient:
    def __init__(self, body):

        self.body = body
        self.requests = []

    def post(self, path, payload):
        self.requests.append((path, payload))

        return ProbeResponse(self.body, 0.5)

    def get(self, path):
        return ProbeResponse({"path": path}, 0.01)


def test_text_probe_requires_exact_content():
    client = StubClient({"message": {"content": "PITHOS_TEXT_OK"}, "eval_count": 2, "eval_duration": 1_000_000_000})

    result = probe_text(client, "test-model")

    assert result["passed"] is True
    assert result["speed_passed"] is True
    assert result["timings"]["decode_tokens_per_second"] == 2.0


def test_structured_probe_parses_json():
    client = StubClient({"message": {"content": '{"status":"ok","value":42}'}})

    result = probe_structured_output(client, "test-model")

    assert result["passed"] is True


def test_tool_probe_rejects_plain_text_serialization():
    client = StubClient({"message": {"content": '{"name":"record_probe","arguments":{"value":42}}'}})

    result = probe_tool_call(client, "test-model")

    assert result["passed"] is False


def test_tool_probe_accepts_native_tool_call():
    client = StubClient(
        {
            "message": {
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "record_probe",
                            "arguments": {"value": 42},
                        }
                    }
                ],
            }
        }
    )

    result = probe_tool_call(client, "test-model")

    assert result["passed"] is True


def test_run_probe_checkpoints_each_scenario(monkeypatch):
    checkpoints = []

    def fake_probe(client, model):
        return {"name": model, "passed": True, "speed_passed": True}

    monkeypatch.setattr("pithos_model_probe.probe.probe_text", fake_probe)
    monkeypatch.setattr("pithos_model_probe.probe.probe_developer_role", fake_probe)
    monkeypatch.setattr("pithos_model_probe.probe.probe_structured_output", fake_probe)
    monkeypatch.setattr("pithos_model_probe.probe.probe_tool_call", fake_probe)

    def record_checkpoint(value):
        checkpoint = value.copy()
        checkpoint["scenarios"] = list(value["scenarios"])
        checkpoints.append(checkpoint)

    result = run_probe(StubClient({}), "test-model", record_checkpoint)

    assert result["complete"] is True
    assert len(checkpoints) == 5
    assert [len(checkpoint["scenarios"]) for checkpoint in checkpoints] == [1, 2, 3, 4, 4]


def test_run_probe_resumes_completed_scenarios(monkeypatch):
    called = []

    def fake_probe(client, model):
        called.append(model)
        return {"name": "tool_call", "passed": True, "speed_passed": True}

    monkeypatch.setattr("pithos_model_probe.probe.probe_tool_call", fake_probe)
    previous_result = {
        "model": "test-model",
        "scenarios": [
            {"name": "text", "passed": True, "speed_passed": True},
            {"name": "developer_role", "passed": True, "speed_passed": True},
            {"name": "structured_output", "passed": False, "speed_passed": False},
        ],
    }

    result = run_probe(StubClient({}), "test-model", previous_result=previous_result)

    assert called == ["test-model"]
    assert len(result["scenarios"]) == 4
