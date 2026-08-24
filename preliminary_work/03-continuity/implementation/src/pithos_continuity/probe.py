"""Prove continuity through two independent Pi processes."""

import json
import os
import shutil
from pathlib import Path

from pithos_capability_probe.runner import classify_protocol, parse_events, run_process_group

from .reports import publish_report


FACT = "PITHOS_CONTINUITY_FACT_42"


def _command(pi: str, provider: str, model: str, session_dir: Path, prompt: str) -> list[str]:
    """Build one non-interactive Pi command using a fresh session directory."""

    return [
        pi,
        "--approve",
        "--provider",
        provider,
        "--model",
        model,
        "--thinking",
        "off",
        "--mode",
        "json",
        "--print",
        "--session-dir",
        str(session_dir),
        prompt,
    ]


def _assistant_text(events: list[dict]) -> str:
    texts = []
    for event in events:
        if event.get("type") != "message_end":
            continue
        message = event.get("message", {})
        if message.get("role") != "assistant":
            continue
        for block in message.get("content", []):
            if block.get("type") == "text":
                texts.append(block.get("text", ""))

    return "\n".join(texts).strip()


def run_probe(
    output_dir: Path,
    logs_root: Path,
    config_dir: Path,
    model: str,
    timeout_seconds: int,
    pi: str = "pi",
    provider: str = "ollama",
) -> dict:
    """Publish a report in one Pi process and recover its fact in another."""

    # isolated roots
    if output_dir.exists():
        shutil.rmtree(output_dir)
    first_workspace = output_dir / "first" / "workspace"
    second_workspace = output_dir / "second" / "workspace"
    first_workspace.mkdir(parents=True)
    second_workspace.mkdir(parents=True)

    # deterministic report contract supplied to the first session
    report = (
        "---\n"
        'schema_version: "1.0"\n'
        "run_id: run-20260824T094000Z-c0ffee\n"
        "experiment_id: continuity-probe\n"
        "micro_rush_id: rush-continuity\n"
        "status: completed\n"
        'started_at: "2026-08-24T11:40:00+02:00"\n'
        'finished_at: "2026-08-24T11:41:00+02:00"\n'
        "branch: agent/rush-continuity\n"
        "commit_before: abcdef1\n"
        "commit_after: abcdef2\n"
        "stop_reason: null\n"
        "next_wake: scheduled\n"
        "---\n\n"
        "## Context\n\n"
        f"The durable fact is {FACT}.\n\n"
        "## Work\n\nCreated the continuity probe report.\n\n"
        "## Next items\n\n- Recover the durable fact in a fresh session.\n"
    )
    (first_workspace / "REPORT_TEMPLATE.md").write_text(report, encoding="utf-8")
    environment = os.environ.copy()
    environment["PI_CODING_AGENT_DIR"] = str(config_dir)

    # first independent session
    first_prompt = "Read REPORT_TEMPLATE.md, then use write to copy it exactly to report.md."
    first_command = _command(pi, provider, model, output_dir / "first" / "sessions", first_prompt)
    first = run_process_group(first_command, first_workspace, environment, timeout_seconds)
    (output_dir / "first" / "stdout.jsonl").write_text(first.stdout, encoding="utf-8")
    (output_dir / "first" / "stderr.log").write_text(first.stderr, encoding="utf-8")
    first_events, first_errors = parse_events(first.stdout)
    first_protocol, first_evidence = classify_protocol(first_events, first_errors)
    report_path = first_workspace / "report.md"
    report_created = report_path.exists()
    if report_created:
        publish_report(report_path, logs_root)

    # only the durable report crosses the session boundary
    shutil.copy2(logs_root / "latest.md", second_workspace / "LATEST.md")
    second_prompt = "Use read on LATEST.md, then reply with only the durable PITHOS_CONTINUITY_FACT marker."
    second_command = _command(pi, provider, model, output_dir / "second" / "sessions", second_prompt)
    second = run_process_group(second_command, second_workspace, environment, timeout_seconds)
    (output_dir / "second" / "stdout.jsonl").write_text(second.stdout, encoding="utf-8")
    (output_dir / "second" / "stderr.log").write_text(second.stderr, encoding="utf-8")
    second_events, second_errors = parse_events(second.stdout)
    second_protocol, second_evidence = classify_protocol(second_events, second_errors)
    recovered = _assistant_text(second_events) == FACT

    result = {
        "model": model,
        "first_process_success": first.exit_code == 0 and not first.timed_out,
        "first_protocol_success": first_protocol,
        "first_protocol_evidence": first_evidence,
        "report_created": report_created,
        "second_process_success": second.exit_code == 0 and not second.timed_out,
        "second_protocol_success": second_protocol,
        "second_protocol_evidence": second_evidence,
        "fact_recovered": recovered,
        "session_directories_distinct": first_command[-2] != second_command[-2],
    }
    (output_dir / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    return result
