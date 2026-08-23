import json
import os
import threading
from dataclasses import replace
from pathlib import Path

import pytest

from pithos_contracts import validate_document, validate_events
from pithos_runner.lock import LockHeld, RunLock
from pithos_runner.runner import LOOP_WARNING, RunnerConfiguration, _runtime_command, run_once
from pithos_runner.state import read_state, write_state
from pithos_runner.events import EventWriter


RUN_ID = "run-20260823T120000Z-a1b2c3"


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
        runtime="host",
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


def test_independent_event_writers_serialize_sequences(tmp_path):
    path = tmp_path / "runs" / "run" / "events.jsonl"

    def append(number):
        EventWriter(path, RUN_ID).append("test.finished", {"number": number})

    threads = [threading.Thread(target=append, args=(number,)) for number in range(20)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    events = [json.loads(line) for line in path.read_text().splitlines()]
    assert [event["sequence"] for event in events] == list(range(20))


def test_pending_telegram_answers_are_claimed_by_the_next_run(tmp_path):
    executable = _executable(
        tmp_path / "answer-pi",
        """
import json
import os
from pathlib import Path

assert 'proceed' in Path('.pithos/ANSWERS.jsonl').read_text()
run_id = os.environ['PITHOS_RUN_ID']
assert os.environ['PITHOS_GIT_SOCKET'].endswith('git.sock')
assert os.environ['PITHOS_HARNESS_SOCKET'].endswith('harness.sock')
assert os.environ['PITHOS_TELEGRAM_SOCKET'].endswith('telegram.sock')
report = f'''---
schema_version: "1.0"
run_id: {run_id}
experiment_id: test-experiment
micro_rush_id: null
status: completed
started_at: "2026-08-23T12:00:00+00:00"
finished_at: "2026-08-23T12:01:00+00:00"
branch: null
commit_before: null
commit_after: null
stop_reason: null
next_wake: scheduled
---
\n## Context\n\nAnswer received.\n\n## Work\n\nApplied.\n\n## Next items\n\n- Continue.\n'''
Path('.pithos/report.md').write_text(report)
for event in ({'type': 'agent_start'}, {'type': 'agent_end', 'messages': []}):
    print(json.dumps(event), flush=True)
""",
    )
    configuration = _configuration(tmp_path, executable)
    ground_truth = tmp_path / "ground-truth"
    journals = tmp_path / "harness-journals"
    ground_truth.mkdir()
    (ground_truth / "AGENTS.md").write_text("constitution")
    (configuration.workspace / "AGENTS.md").write_text("active")
    configuration = replace(
        configuration,
        git_socket=tmp_path / "git.sock",
        harness_socket=tmp_path / "harness.sock",
        telegram_socket=tmp_path / "telegram.sock",
        ground_truth_root=ground_truth,
        harness_journals_root=journals,
    )
    answers = configuration.logs_root / "runtime" / "answers.jsonl"
    answers.parent.mkdir(parents=True)
    answers.write_text(json.dumps({"run_id": RUN_ID, "answer": "proceed"}) + "\n")

    result = run_once(configuration)

    run_dir = configuration.logs_root / "runs" / result["run_id"]
    assert result["status"] == "completed"
    assert (run_dir / "telegram-answers.jsonl").exists()
    assert not answers.exists()
    assert (journals / result["run_id"] / "before" / "AGENTS.md").exists()
    assert (journals / result["run_id"] / "after" / "AGENTS.md").exists()


def test_docker_runtime_mounts_only_scoped_paths_and_forwards_no_secrets(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "logs" / "runs" / RUN_ID
    config_dir = tmp_path / "pi-config"
    for path in (workspace, run_dir, config_dir):
        path.mkdir(parents=True)
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-leak")
    configuration = RunnerConfiguration(
        experiment_id="test",
        workspace=workspace,
        logs_root=tmp_path / "logs",
        pi_config_dir=config_dir,
    )

    command, environment = _runtime_command(configuration, RUN_ID, run_dir, "work")
    rendered = " ".join(command)

    assert command[:2] == ["docker", "run"]
    assert "--network pithos-agent" in rendered
    assert f"src={workspace},dst=/workspace" in rendered
    assert f"http://{RUN_ID}@pithos-egress:3128" in rendered
    assert "must-not-leak" not in rendered
    assert "OPENAI_API_KEY" not in environment
    assert "HOME" not in environment


def test_docker_runtime_rejects_secret_bearing_pi_config(tmp_path):
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "logs" / "runs" / RUN_ID
    config_dir = tmp_path / "pi-config"
    for path in (workspace, run_dir, config_dir):
        path.mkdir(parents=True)
    (config_dir / "auth.json").write_text('{"token":"secret"}')
    configuration = RunnerConfiguration(
        experiment_id="test",
        workspace=workspace,
        logs_root=tmp_path / "logs",
        pi_config_dir=config_dir,
    )

    with pytest.raises(ValueError, match="forbidden"):
        _runtime_command(configuration, RUN_ID, run_dir, "work")


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
    assert result["success"]["task"] is True
    run_dir = configuration.logs_root / "runs" / result["run_id"]
    validate_document(json.loads((run_dir / "run.json").read_text()), "run")
    assert validate_events(run_dir / "events.jsonl") == 4
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
