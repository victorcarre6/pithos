import importlib.util
from pathlib import Path

from fastapi.testclient import TestClient

from pithos_event_store import EventStore
from pithos_runner.runner import RunnerConfiguration, run_once


DASHBOARD_APP = Path(__file__).parents[1] / "dashboard" / "api" / "app.py"


def _fake_pi(path):
    path.write_text(
        """#!/usr/bin/env python3
import json
import os
from pathlib import Path

run_id = os.environ["PITHOS_RUN_ID"]
report = f'''---
schema_version: "1.0"
run_id: {run_id}
experiment_id: integration
micro_rush_id: rush-observe
status: completed
started_at: "2026-08-23T12:00:00+00:00"
finished_at: "2026-08-23T12:01:00+00:00"
branch: agent/rush-observe
commit_before: aaaaaaa
commit_after: bbbbbbb
stop_reason: null
next_wake: scheduled
---

## Context

Integration run.

## Work

Observed Pi.

## Next items

- Continue.
'''
Path('.pithos/report.md').write_text(report)
events = [
    {"type": "session", "id": "session-integration"},
    {"type": "agent_start"},
    {
        "type": "message_end",
        "message": {
            "role": "assistant",
            "content": [{"type": "text", "text": "Running tests."}],
            "usage": {"input": 20, "output": 5, "totalTokens": 25},
        },
    },
    {
        "type": "tool_execution_start",
        "toolCallId": "call-1",
        "toolName": "bash",
        "args": {"command": "pytest -q"},
    },
    {
        "type": "tool_execution_end",
        "toolCallId": "call-1",
        "toolName": "bash",
        "result": {"content": "1 passed"},
        "isError": False,
    },
    {"type": "agent_end", "messages": []},
]
for event in events:
    print(json.dumps(event), flush=True)
""",
        encoding="utf-8",
    )
    path.chmod(0o755)

    return path


def _dashboard(database, logs_root):
    spec = importlib.util.spec_from_file_location("pithos_dashboard_integration", DASHBOARD_APP)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.DATABASE_PATH = database
    module.LOGS_ROOT = logs_root

    return TestClient(module.app)


def test_pi_events_flow_through_sqlite_and_dashboard(tmp_path):
    executable = _fake_pi(tmp_path / "fake-pi")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    pi_config = tmp_path / "pi-config"
    pi_config.mkdir()
    logs_root = tmp_path / "logs"
    configuration = RunnerConfiguration(
        experiment_id="integration",
        workspace=workspace,
        logs_root=logs_root,
        pi_config_dir=pi_config,
        pi_executable=str(executable),
        provider="fake",
        model="fake",
        timeout_seconds=5,
        runtime="host",
    )

    run = run_once(configuration)
    events_path = logs_root / "runs" / run["run_id"] / "events.jsonl"
    database = logs_root / "pithos.db"
    store = EventStore(database)
    ingestion = store.ingest(events_path)
    store.close()
    client = _dashboard(database, logs_root)

    stats = client.get("/api/stats").json()
    commands = client.get(f"/api/runs/{run['run_id']}/events?domain=command").json()
    report = client.get(f"/api/runs/{run['run_id']}/artifacts/report.md").json()

    assert ingestion["quarantined"] == 0
    assert run["success"] == {
        "process": True,
        "protocol": True,
        "task": True,
        "report": True,
    }
    assert run["micro_rush_id"] == "rush-observe"
    assert stats["total_tokens"] == 25
    assert stats["tool_failures"] == 0
    assert commands["items"][0]["payload"]["command"] == "pytest -q"
    assert "## Next items" in report["content"]
