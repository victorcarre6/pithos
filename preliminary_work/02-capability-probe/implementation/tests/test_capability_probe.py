import json
from pathlib import Path

from pithos_capability_probe.runner import (
    PiConfiguration,
    classify_protocol,
    parse_events,
    run_process_group,
    run_scenario,
)
from pithos_capability_probe.scenarios import SCENARIOS


def test_parse_events_preserves_malformed_lines():
    events, errors = parse_events('{"type":"agent_start"}\nnot-json\n')

    assert events == [{"type": "agent_start"}]
    assert errors and errors[0].startswith("line 2")


def test_protocol_rejects_text_serialized_tool_call():
    events = [
        {"type": "agent_start"},
        {
            "type": "message_end",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": '{"name":"read","arguments":{"path":"x"}}'}],
            },
        },
        {"type": "agent_end"},
    ]

    passed, evidence = classify_protocol(events, [])

    assert passed is False
    assert "serialized" in evidence


def test_protocol_requires_balanced_tool_events():
    events = [
        {"type": "agent_start"},
        {"type": "tool_execution_start", "toolCallId": "call-1"},
        {"type": "agent_end"},
    ]

    passed, evidence = classify_protocol(events, [])

    assert passed is False
    assert "unbalanced" in evidence


def _fake_pi(path: Path) -> None:
    script = """#!/usr/bin/env python3
import json
from pathlib import Path

Path('created.txt').write_text('PITHOS_WRITE_OK\\n')
events = [
    {'type': 'session', 'version': 3, 'id': 'fake'},
    {'type': 'agent_start'},
    {'type': 'tool_execution_start', 'toolCallId': 'call-1', 'toolName': 'write', 'args': {}},
    {'type': 'tool_execution_end', 'toolCallId': 'call-1', 'toolName': 'write', 'result': {}, 'isError': False},
    {'type': 'agent_end', 'messages': []},
]
for event in events:
    print(json.dumps(event))
"""
    path.write_text(script)
    path.chmod(0o755)


def test_run_scenario_verifies_real_effect(tmp_path):
    fake_pi = tmp_path / "fake-pi"
    _fake_pi(fake_pi)
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    configuration = PiConfiguration(
        executable=str(fake_pi),
        provider="fake",
        model="fake",
        timeout_seconds=2,
        config_dir=config_dir,
    )

    result = run_scenario(tmp_path / "result", SCENARIOS["write"], configuration)

    assert result["process_success"] is True
    assert result["protocol_success"] is True
    assert result["task_success"] is True
    persisted_events = (tmp_path / "result" / "stdout.jsonl").read_text().splitlines()
    assert json.loads(persisted_events[0])["type"] == "session"


def test_process_group_is_terminated_on_timeout(tmp_path):
    sleeper = tmp_path / "sleeper"
    sleeper.write_text("#!/bin/sh\nsleep 30 &\nwait\n")
    sleeper.chmod(0o755)

    outcome = run_process_group(
        [str(sleeper)],
        cwd=tmp_path,
        environment={},
        timeout_seconds=0.1,
    )

    assert outcome.timed_out is True
    assert outcome.exit_code is None
