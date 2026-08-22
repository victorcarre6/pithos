import json
import os
from dataclasses import replace
from pathlib import Path

import pytest

from pithos_contracts import validate_document, validate_events
from pithos_runner.lock import LockHeld, RunLock
from pithos_runner.runner import LOOP_WARNING, RunnerConfiguration, run_once
from pithos_runner.state import read_state, write_state


def _executable(path: Path, body: str) -> Path:
    path.write_text(f"#!/usr/bin/env python3\n{body}")
    path.chmod(0o755)

    return path


def _configuration(tmp_path: Path, executable: Path, timeout=2, repeat_limit=3, heartbeat=30):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    config_dir = tmp_path / "pi-config"
    config_dir.mkdir()

    return RunnerConfiguration(
        experiment_id="test-experiment",
        workspace=workspace,
        logs_root=tmp_path / "logs",
        pi_config_dir=config_dir,
        pi_executable=str(executable),
        provider="fake",
        model="fake",
        timeout_seconds=timeout,
        repeat_limit=repeat_limit,
        heartbeat_seconds=heartbeat,
    )


def test_lock_refuses_live_owner(tmp_path):
    lock_path = tmp_path / "runner.lock"
    lock_path.mkdir()
    (lock_path / "owner.json").write_text(json.dumps({"pid": os.getpid()}))

    with pytest.raises(LockHeld, match="live PID"):
        RunLock(lock_path).acquire()


def test_lock_recovers_dead_owner(tmp_path):
    lock_path = tmp_path / "runner.lock"
    lock_path.mkdir()
    (lock_path / "owner.json").write_text(json.dumps({"pid": 999_999_999}))
    lock = RunLock(lock_path)

    lock.acquire()
    lock.release()

    assert not lock_path.exists()


def test_pause_state_survives_new_reads(tmp_path):
    state_path = tmp_path / "state.json"

    write_state(state_path, True, LOOP_WARNING)

    assert read_state(state_path)["paused"] is True
    assert read_state(state_path)["reason"] == LOOP_WARNING


def test_runner_completes_only_with_valid_report(tmp_path):
    executable = _executable(
        tmp_path / "fake-pi",
        """
import json
import os
from pathlib import Path

run_id = os.environ['PITHOS_RUN_ID']
report = f'''---
schema_version: "1.0"
run_id: {run_id}
experiment_id: test-experiment
micro_rush_id: null
status: completed
started_at: "2026-08-22T20:00:00+00:00"
finished_at: "2026-08-22T20:01:00+00:00"
branch: null
commit_before: null
commit_after: null
stop_reason: null
next_wake: scheduled
---

## Context

Deterministic runner test.

## Work

Created a valid report.

## Next items

- Continue.
'''
Path('.pithos/report.md').write_text(report)
for event in ({'type': 'agent_start'}, {'type': 'agent_end', 'messages': []}):
    print(json.dumps(event), flush=True)
""",
    )
    configuration = _configuration(tmp_path, executable)

    result = run_once(configuration)

    assert result["status"] == "completed"
    assert result["success"]["report"] is True
    run_dir = configuration.logs_root / "runs" / result["run_id"]
    validate_document(json.loads((run_dir / "run.json").read_text()), "run")
    assert validate_events(run_dir / "events.jsonl") == 2
    assert (configuration.logs_root / "latest.md").exists()


def test_runner_times_out_process_group(tmp_path):
    executable = _executable(
        tmp_path / "slow-pi",
        """
import subprocess
import time

subprocess.Popen(['sleep', '30'])
time.sleep(30)
""",
    )
    configuration = _configuration(tmp_path, executable, timeout=0.15, heartbeat=0.05)

    result = run_once(configuration)

    assert result["status"] == "timed_out"
    assert result["success"]["process"] is False
    run_dir = configuration.logs_root / "runs" / result["run_id"]
    events = [json.loads(line) for line in (run_dir / "events.jsonl").read_text().splitlines()]
    assert "run.heartbeat" in {event["type"] for event in events}


def test_loop_guard_notifies_then_pauses_even_if_notification_fails(tmp_path, monkeypatch):
    executable = _executable(
        tmp_path / "loop-pi",
        """
import json
import time

print(json.dumps({'type': 'agent_start'}), flush=True)
for index in range(5):
    call_id = f'call-{index}'
    print(json.dumps({'type': 'tool_execution_start', 'toolCallId': call_id, 'toolName': 'read', 'args': {'path': 'same.txt'}}), flush=True)
    print(json.dumps({'type': 'tool_execution_end', 'toolCallId': call_id, 'toolName': 'read', 'isError': True, 'result': {}}), flush=True)
    time.sleep(0.02)
time.sleep(30)
""",
    )
    configuration = _configuration(tmp_path, executable, repeat_limit=3)
    configuration = replace(configuration, telegram_socket=tmp_path / "missing.sock")
    attempts = []

    def unavailable(socket_path, request):
        attempts.append((socket_path, request))
        raise OSError("Telegram unavailable")

    monkeypatch.setattr("pithos_telegram.client.send_request", unavailable)

    result = run_once(configuration)

    assert attempts[0][1]["text"] == "Boucle récursive infinie détectée."
    assert result["status"] == "paused"
    assert result["stop_reason"] == LOOP_WARNING
    assert read_state(configuration.logs_root / "runtime" / "state.json")["paused"] is True
    with pytest.raises(RuntimeError, match="paused"):
        run_once(configuration)
