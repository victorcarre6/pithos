import json

from pithos_runner.events import EventWriter
from pithos_runner.pi_events import PiEventAdapter


RUN_ID = "run-20260823T120000Z-a1b2c3"


def _consume(adapter, event):
    adapter.consume_line(json.dumps(event))


def test_messages_tools_and_metrics_are_projected(tmp_path):
    path = tmp_path / "runs" / RUN_ID / "events.jsonl"
    adapter = PiEventAdapter(EventWriter(path, RUN_ID, source="pi"))
    _consume(
        adapter,
        {
            "type": "message_end",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "done"}],
                "usage": {"input": 10, "output": 4, "totalTokens": 14},
            },
        },
    )
    _consume(
        adapter,
        {"type": "tool_execution_start", "toolCallId": "call-1", "toolName": "bash", "args": {"command": "pytest -q"}},
    )
    _consume(
        adapter,
        {"type": "tool_execution_end", "toolCallId": "call-1", "toolName": "bash", "args": {"command": "pytest -q"}, "result": {"text": "ok"}, "isError": False},
    )

    events = [json.loads(line) for line in path.read_text().splitlines()]
    assert {
        "model.response",
        "tool.started",
        "tool.finished",
        "command.finished",
        "test.finished",
    }.issubset({event["type"] for event in events})
    assert adapter.metrics() == {
        "input_tokens": 10,
        "output_tokens": 4,
        "total_tokens": 14,
        "tool_calls": 1,
        "tool_failures": 0,
    }


def test_file_dependency_and_network_effects_are_classified(tmp_path):
    path = tmp_path / "runs" / RUN_ID / "events.jsonl"
    adapter = PiEventAdapter(EventWriter(path, RUN_ID, source="pi"))
    _consume(
        adapter,
        {"type": "tool_execution_end", "toolCallId": "write-1", "toolName": "write", "args": {"path": "app.py"}, "result": {}, "isError": False},
    )
    _consume(
        adapter,
        {"type": "tool_execution_end", "toolCallId": "bash-1", "toolName": "bash", "args": {"command": "python -m pip install demo"}, "result": {}, "isError": True},
    )

    event_types = [json.loads(line)["type"] for line in path.read_text().splitlines()]
    assert "file.changed" in event_types
    assert "dependency.installed" in event_types
    assert "network.requested" in event_types
    assert adapter.metrics()["tool_failures"] == 1


def test_malformed_pi_output_is_preserved_without_stopping_stream(tmp_path):
    path = tmp_path / "runs" / RUN_ID / "events.jsonl"
    adapter = PiEventAdapter(EventWriter(path, RUN_ID, source="pi"))

    adapter.consume_line("not-json")

    event = json.loads(path.read_text())
    assert event["type"] == "pi.protocol_error"
    assert event["payload"]["line"] == "not-json"
