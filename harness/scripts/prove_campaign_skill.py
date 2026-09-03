#!/usr/bin/env python3
"""Create, promote and cognitively reuse one skill in a real Pithos campaign workspace."""

import argparse
import json
import os
import shutil
from pathlib import Path

from pithos_capability_probe.runner import classify_protocol, parse_events, run_process_group
from pithos_harness import HarnessManager
from pithos_runner.events import EventWriter
from pithos_runner.pi_events import PiEventAdapter
from pithos_runner.runner import new_run_id


SKILL_NAME = "pithos-campaign-proof"
MARKER = "PITHOS_CAMPAIGN_SKILL_REUSED"
SKILL_CONTENT = (
    "---\n"
    f"name: {SKILL_NAME}\n"
    "description: Return the deterministic campaign capability marker.\n"
    "---\n\n"
    "# Campaign proof skill\n\n"
    f"When asked for the campaign capability marker, reply exactly {MARKER}.\n"
)


def prove(workspace, logs_root, journals_root, ground_truth, config_dir, model, pi="pi", timeout=300):
    """Run the two-session campaign proof and return its persisted result."""

    # état et preuve primaire
    workspace = Path(workspace).resolve()
    logs_root = Path(logs_root).expanduser().resolve()
    project = json.loads((workspace / ".pithos.json").read_text(encoding="utf-8"))
    experiment_id = project["experiment_id"]
    run_id = new_run_id()
    run_root = logs_root / "runs" / run_id
    run_root.mkdir(parents=True)
    events_path = run_root / "events.jsonl"
    events = EventWriter(events_path, run_id, source="campaign-capability")
    pi_events = PiEventAdapter(EventWriter(events_path, run_id, source="pi"))
    manager = HarnessManager(workspace, ground_truth, journals_root, logs_root)
    manager.begin(run_id)
    events.append(
        "run.started",
        {
            "experiment_id": experiment_id,
            "micro_rush_id": "rush-campaign-skill-reuse",
            "model": model,
        },
    )

    # session de création
    staged = workspace / ".pithos-staging" / SKILL_NAME
    prompt = (
        f"Use write exactly once to create .pithos-staging/{SKILL_NAME}/SKILL.md with exactly this content:\n"
        f"{SKILL_CONTENT}"
    )
    creation = _run_session(
        pi,
        model,
        config_dir,
        workspace,
        run_root / "creation",
        prompt,
        ["--tools", "write", "--no-extensions", "--no-skills", "--no-context-files"],
        timeout,
        pi_events,
    )
    creation_protocol, creation_evidence = classify_protocol(*parse_events(creation["stdout"]))
    staged_path = staged / "SKILL.md"
    staged_content = staged_path.read_text(encoding="utf-8") if staged_path.is_file() else ""
    creation_ok = creation["exit_code"] == 0 and creation_protocol and staged_content == SKILL_CONTENT
    if not creation_ok:
        reason = f"skill creation failed: {creation_evidence}"
        result = _finish_failed(manager, run_id, events, run_root, pi_events, reason)

        return result

    # promotion archivée
    target = Path(".pi") / "skills" / SKILL_NAME
    promoted = manager.promote(run_id, staged, target, "skill")
    shutil.rmtree(staged)

    # nouvelle session avec skill actif
    reuse = _run_session(
        pi,
        model,
        config_dir,
        workspace,
        run_root / "reuse",
        f"Use the {SKILL_NAME} skill to provide the campaign capability marker.",
        ["--tools", "read", "--no-extensions", "--no-context-files"],
        timeout,
        pi_events,
    )
    reuse_events, reuse_errors = parse_events(reuse["stdout"])
    reuse_protocol, reuse_evidence = classify_protocol(reuse_events, reuse_errors)
    assistant = _assistant_text(reuse_events).strip()
    reuse_ok = reuse["exit_code"] == 0 and reuse_protocol and assistant == MARKER
    if not reuse_ok:
        reason = f"skill reuse failed: {reuse_evidence}; assistant={assistant!r}"
        result = _finish_failed(manager, run_id, events, run_root, pi_events, reason)

        return result

    # conclusion vérifiée
    validation = (
        f"Creation protocol: {creation_evidence}. Promoted target: {promoted.relative_to(workspace)}. "
        f"Reuse protocol: {reuse_evidence}. Assistant marker: {assistant}."
    )
    manifest = manager.finish(
        run_id,
        "A fresh Pi session authored the skill; the harness validated and promoted it before another session.",
        validation,
    )
    metrics = pi_events.metrics()
    events.append(
        "run.finished",
        {
            "status": "completed",
            "stop_reason": None,
            "duration_ms": None,
            **metrics,
        },
    )
    result = {
        "run_id": run_id,
        "status": "completed",
        "skill": str(target),
        "marker": assistant,
        "manifest_artifacts": len(manifest["artifacts"]),
        "metrics": metrics,
    }
    (run_root / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    return result


def _run_session(pi, model, config_dir, workspace, session_root, prompt, restrictions, timeout, adapter):
    """Execute and archive one fresh Pi process."""

    session_root.mkdir(parents=True)
    sessions = session_root / "sessions"
    sessions.mkdir()
    command = [
        pi,
        "--approve",
        "--provider",
        "ollama",
        "--model",
        model,
        "--thinking",
        "off",
        "--mode",
        "json",
        "--print",
        "--session-dir",
        str(sessions),
        *restrictions,
        prompt,
    ]
    environment = os.environ.copy()
    environment["PI_CODING_AGENT_DIR"] = str(Path(config_dir).resolve())
    outcome = run_process_group(command, workspace, environment, timeout)
    (session_root / "stdout.jsonl").write_text(outcome.stdout, encoding="utf-8")
    (session_root / "stderr.log").write_text(outcome.stderr, encoding="utf-8")
    for line in outcome.stdout.splitlines():
        adapter.consume_line(line)

    return {
        "command": command[:-1],
        "exit_code": outcome.exit_code,
        "timed_out": outcome.timed_out,
        "stdout": outcome.stdout,
        "stderr": outcome.stderr,
    }


def _assistant_text(events):
    """Join assistant text blocks from Pi JSON events."""

    texts = []
    for event in events:
        if event.get("type") != "message_end":
            continue
        message = event.get("message") or {}
        if message.get("role") != "assistant":
            continue
        for block in message.get("content") or []:
            if block.get("type") == "text":
                texts.append(str(block.get("text") or ""))

    return "\n".join(texts)


def _finish_failed(manager, run_id, events, run_root, adapter, reason):
    """Archive one failed proof without rewriting its evidence."""

    manager.finish(run_id, "The campaign capability proof did not complete.", reason)
    metrics = adapter.metrics()
    events.append(
        "run.finished",
        {
            "status": "failed",
            "stop_reason": reason,
            "duration_ms": None,
            **metrics,
        },
    )
    result = {
        "run_id": run_id,
        "status": "failed",
        "reason": reason,
        "metrics": metrics,
    }
    (run_root / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    return result


def main():
    """Run the campaign proof from one experiment configuration."""

    parser = argparse.ArgumentParser(description="Prove skill promotion and reuse in one campaign workspace")
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--logs-root", type=Path, default=Path.home() / "logs" / "pithos")
    parser.add_argument("--journals-root", type=Path, default=Path(__file__).resolve().parents[2] / "journals" / "harness")
    parser.add_argument("--pi", default="pi")
    parser.add_argument("--timeout-seconds", type=int, default=300)
    arguments = parser.parse_args()
    project = json.loads((arguments.workspace / ".pithos.json").read_text(encoding="utf-8"))
    result = prove(
        arguments.workspace,
        arguments.logs_root,
        arguments.journals_root,
        Path(project["ground_truth"]),
        Path(project["pi_config"]),
        project.get("model", "maternion/ling-3.0-tiny:8b"),
        pi=arguments.pi,
        timeout=arguments.timeout_seconds,
    )
    print(json.dumps(result, indent=2))

    return 0 if result["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
