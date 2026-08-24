import json
import sys
from pathlib import Path

from pithos_capability_probe import cli
from pithos_capability_probe.runner import (
    PiConfiguration,
    classify_protocol,
    parse_events,
    run_process_group,
    run_scenario,
)
from pithos_capability_probe.scenarios import SCENARIOS, Scenario


def test_cli_all_accepts_no_positional_scenario(monkeypatch, tmp_path):
    results = []

    def fake_run_scenario(result_dir, scenario, configuration):
        result_dir.mkdir(parents=True)
        results.append(scenario.name)

        return {
            "process_success": True,
            "protocol_success": True,
            "task_success": True,
        }

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    arguments = [
        "pithos-capability-probe",
        "--all",
        "--config-dir",
        str(config_dir),
        "--output-dir",
        str(tmp_path / "output"),
    ]
    monkeypatch.setattr(sys, "argv", arguments)
    monkeypatch.setattr(cli, "run_scenario", fake_run_scenario)

    assert cli.main() == 0
    assert results == list(SCENARIOS)


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


def test_run_scenario_uses_a_fresh_process_for_follow_up(tmp_path):
    fake_pi = tmp_path / "fake-pi"
    fake_pi.write_text(
        """#!/usr/bin/env python3
import json
import sys
from pathlib import Path

prompt = sys.argv[-1]
if prompt == 'create':
    Path('marker.txt').write_text('created')
text = 'PITHOS_REUSED' if prompt == 'reuse' and Path('marker.txt').exists() else 'initial'
events = [
    {'type': 'agent_start'},
    {'type': 'message_end', 'message': {'role': 'assistant', 'content': [{'type': 'text', 'text': text}]}},
    {'type': 'agent_end'},
]
for event in events:
    print(json.dumps(event))
"""
    )
    fake_pi.chmod(0o755)
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    configuration = PiConfiguration(str(fake_pi), "fake", "fake", 2, config_dir)

    def verify(workspace, events):
        assistant = events[1]["message"]["content"][0]["text"]

        return assistant == "PITHOS_REUSED", assistant

    scenario = Scenario("restart", "create", lambda path: path.mkdir(), verify, follow_up_prompt="reuse")

    result = run_scenario(tmp_path / "result", scenario, configuration)

    assert result["process_success"] is True
    assert result["protocol_success"] is True
    assert result["task_success"] is True
    assert (tmp_path / "result" / "stdout.initial.jsonl").is_file()
    assert (tmp_path / "result" / "stdout.follow-up.jsonl").is_file()


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
