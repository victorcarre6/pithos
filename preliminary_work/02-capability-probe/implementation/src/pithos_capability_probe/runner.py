"""Execute Pi in a fresh workspace and classify process, protocol and task success."""

import json
import os
import signal
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .scenarios import SCENARIOS, Scenario, prepare_report_template


@dataclass(frozen=True)
class PiConfiguration:
    """Parameters controlled by the capability probe caller."""

    executable: str
    provider: str
    model: str
    timeout_seconds: int
    config_dir: Path


@dataclass(frozen=True)
class ProcessOutcome:
    """Capture a process group result, including enforced timeout state."""

    exit_code: int | None
    stdout: str
    stderr: str
    timed_out: bool


def parse_events(stdout: str) -> tuple[list[dict], list[str]]:
    """Decode Pi JSON mode while preserving malformed lines as protocol errors."""

    events = []
    errors = []

    for line_number, raw_line in enumerate(stdout.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as error:
            errors.append(f"line {line_number}: {error}")
            continue
        if not isinstance(event, dict):
            errors.append(f"line {line_number}: event is not an object")
            continue
        events.append(event)

    return events, errors


def classify_protocol(events: list[dict], parse_errors: list[str]) -> tuple[bool, str]:
    """Require balanced tool events and reject tool calls emitted as plain text."""

    if parse_errors:
        return False, "; ".join(parse_errors)

    starts = {
        event.get("toolCallId")
        for event in events
        if event.get("type") == "tool_execution_start"
    }
    ends = {
        event.get("toolCallId")
        for event in events
        if event.get("type") == "tool_execution_end"
    }

    if starts != ends:
        return False, f"unbalanced tool executions: starts={starts}, ends={ends}"

    text_blocks = []
    for event in events:
        if event.get("type") != "message_end":
            continue
        for block in event.get("message", {}).get("content", []):
            if block.get("type") == "text":
                text_blocks.append(block.get("text", ""))
    serialized_text = "\n".join(text_blocks)
    looks_like_tool_json = '"name"' in serialized_text and '"arguments"' in serialized_text

    if looks_like_tool_json and not starts:
        return False, "assistant serialized a tool call as text"

    has_lifecycle = any(event.get("type") == "agent_start" for event in events)
    has_end = any(event.get("type") == "agent_end" for event in events)

    return has_lifecycle and has_end, f"tool_executions={len(ends)}"


def _prepare_workspace(root: Path, scenario: Scenario) -> Path:
    workspace = root / "workspace"
    if workspace.exists():
        shutil.rmtree(workspace)
    scenario.prepare(workspace)
    if scenario.report_expected:
        prepare_report_template(workspace)

    return workspace


def run_process_group(
    command: list[str],
    cwd: Path,
    environment: dict[str, str],
    timeout_seconds: int,
) -> ProcessOutcome:
    """Run a command in its own process group and terminate all descendants on timeout."""

    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )

    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)

        return ProcessOutcome(process.returncode, stdout, stderr, False)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            stdout, stderr = process.communicate()

        return ProcessOutcome(None, stdout, stderr, True)


def run_scenario(root: Path, scenario: Scenario, configuration: PiConfiguration) -> dict:
    """Run one isolated Pi process and verify its effects externally."""

    root.mkdir(parents=True, exist_ok=True)
    workspace = _prepare_workspace(root, scenario)
    session_dir = root / "sessions"
    session_dir.mkdir(exist_ok=True)
    command = [
        configuration.executable,
        "--approve",
        "--provider",
        configuration.provider,
        "--model",
        configuration.model,
        "--thinking",
        "off",
        "--mode",
        "json",
        "--print",
        "--session-dir",
        str(session_dir),
        scenario.prompt,
    ]
    environment = os.environ.copy()
    environment["PI_CODING_AGENT_DIR"] = str(configuration.config_dir)

    outcome = run_process_group(
        command,
        cwd=workspace,
        environment=environment,
        timeout_seconds=configuration.timeout_seconds,
    )
    exit_code = outcome.exit_code
    stdout = outcome.stdout
    stderr = outcome.stderr
    timed_out = outcome.timed_out

    (root / "stdout.jsonl").write_text(stdout, encoding="utf-8")
    (root / "stderr.log").write_text(stderr, encoding="utf-8")
    events, parse_errors = parse_events(stdout)
    protocol_success, protocol_evidence = classify_protocol(events, parse_errors)
    task_success, task_evidence = scenario.verify(workspace, events)
    report_success = task_success if scenario.report_expected else None

    return {
        "scenario": scenario.name,
        "process_success": exit_code == 0 and not timed_out,
        "protocol_success": protocol_success,
        "task_success": task_success,
        "report_success": report_success,
        "exit_code": exit_code,
        "timed_out": timed_out,
        "protocol_evidence": protocol_evidence,
        "task_evidence": task_evidence,
        "command": command,
    }
