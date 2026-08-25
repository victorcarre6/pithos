"""Execute one bounded fresh Pi session for an orchestration phase."""

import json
import os
import hashlib
import re
import shutil
import urllib.request
from dataclasses import replace
from dataclasses import dataclass
from pathlib import Path

from pithos_capability_probe.runner import classify_protocol, parse_events
from pithos_runner.pi_events import PiEventAdapter
from pithos_runner.process import run_monitored
from pithos_runner.runner import RunnerConfiguration, _runtime_command

from .controller import PhaseResult


_DEF = re.compile(r"(?m)^\s*def\s+[A-Za-z_][A-Za-z0-9_]*\s*\(")


@dataclass(frozen=True)
class PhaseBudget:
    """Hard process and tool limits for one fresh Pi session."""

    timeout_seconds: int = 300
    repeat_limit: int = 3
    max_tool_calls: int = 8


class PiPhaseRunner:
    """Run Pi without requiring continuity, Git or report completion inside the session."""

    def __init__(self, configuration, mission_root, events, budget=None):
        self.configuration = configuration
        self.mission_root = Path(mission_root)
        self.events = events
        self.budget = budget or PhaseBudget()
        self.sequence = 0

    def __call__(self, phase, context):
        self.sequence += 1
        phase_dir = self.mission_root / "phases" / f"{self.sequence:02d}-{phase}"
        phase_dir.mkdir(parents=True)
        (phase_dir / "sessions").mkdir()
        projection = phase_dir / "workspace"
        projection.mkdir()
        allowed_paths = _context_paths(context)
        _prepare_projection(self.configuration.workspace, projection, allowed_paths)
        phase_configuration = replace(self.configuration, workspace=projection)
        prompt = _phase_prompt(phase, context)
        command, environment = _runtime_command(
            phase_configuration,
            os.environ.get("PITHOS_RUN_ID", self.mission_root.name),
            phase_dir,
            prompt,
        )
        command[-1:-1] = [
            "--tools",
            "edit,write",
            "--no-extensions",
            "--no-skills",
            "--no-context-files",
        ]
        before = _workspace_files(projection)
        adapter = PiEventAdapter(self.events)
        outcome = run_monitored(
            command,
            cwd=projection,
            environment=environment,
            stdout_path=phase_dir / "stdout.jsonl",
            stderr_path=phase_dir / "stderr.log",
            timeout_seconds=self.budget.timeout_seconds,
            repeat_limit=self.budget.repeat_limit,
            on_stdout_line=adapter.consume_line,
            max_tool_calls=self.budget.max_tool_calls,
        )
        if outcome.timed_out or outcome.tool_limit_exceeded:
            _release_ollama_model(self.configuration)
        stdout = (phase_dir / "stdout.jsonl").read_text(encoding="utf-8")
        pi_events, parse_errors = parse_events(stdout)
        protocol_success, _ = classify_protocol(pi_events, parse_errors)
        stream_valid = not parse_errors and any(event.get("type") == "agent_start" for event in pi_events)
        after = _workspace_files(projection)
        changed_files = sorted(
            path
            for path in allowed_paths
            if before.get(path) != after.get(path)
        )
        # a weak model can `write` a malformed tool call as if it were file content (observed:
        # a bare {"action": "check_file", ...} blob replacing a whole module) -- never let that
        # reach the host workspace, where it would silently destroy previously-working code.
        valid_changes = _valid_python_changes(self.configuration.workspace, projection, changed_files)
        if valid_changes:
            _apply_projection(projection, self.configuration.workspace, changed_files)
        else:
            changed_files = []

        productive_stop = outcome.exit_code == 0 or outcome.timed_out or outcome.tool_limit_exceeded
        protocol_gate = protocol_success if outcome.exit_code == 0 else stream_valid
        success = productive_stop and protocol_gate and not outcome.loop_detected and valid_changes
        summary = _summary(phase, success, outcome, adapter.metrics())
        if not valid_changes:
            summary += " invalid_python"
        result = {
            "phase": phase,
            "success": success,
            "summary": summary,
            "changed_files": changed_files,
            "metrics": adapter.metrics(),
        }
        (phase_dir / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

        return PhaseResult(success, summary, changed_files)


def _phase_prompt(phase, context):
    instructions = {
        "implement": "Implement only the requested change using the files already included below. Do not inventory the workspace.",
        "repair": (
            "The external validation failure is authoritative. Fix only the explicitly targeted file. "
            "Existing comments, annotations and helpers may describe obsolete behavior; replace them when "
            "they conflict with the contract. Do not create alternative files or directories."
        ),
        "review": "Review the included implementation against the contract. Fix only a demonstrated mismatch; otherwise finish immediately.",
    }

    return f"{instructions[phase]}\n\n{context}"


def _summary(phase, success, outcome, metrics):
    status = "completed" if success else "failed"
    if outcome.timed_out:
        status = "timed_out"
    if outcome.loop_detected:
        status = "loop_detected"
    if outcome.tool_limit_exceeded:
        status = "tool_limit"

    return (
        f"phase={phase} status={status} tool_calls={metrics['tool_calls']} "
        f"tokens={metrics['total_tokens']}"
    )


def _workspace_files(workspace):
    files = {}
    ignored = {".git", ".pytest_cache", "__pycache__", ".pithos"}
    for path in Path(workspace).rglob("*"):
        if not path.is_file() or any(part in ignored for part in path.parts):
            continue
        relative = str(path.relative_to(workspace))
        files[relative] = hashlib.sha256(path.read_bytes()).hexdigest()

    return files


def _context_paths(context):
    paths = []
    for line in context.splitlines():
        if not line.startswith("## File: "):
            continue
        relative = line.removeprefix("## File: ").strip()
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts:
            continue
        paths.append(relative)

    return sorted(set(paths))


def _prepare_projection(workspace, projection, allowed_paths):
    for relative in allowed_paths:
        source = Path(workspace) / relative
        if not source.is_file():
            continue
        destination = projection / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def _valid_python_changes(workspace, projection, changed_files):
    """Reject the whole batch if any changed `.py` file no longer parses, or lost every
    function definition it used to have -- a bare `write` of e.g. a stray tool-call blob
    is syntactically valid Python (an expression statement) but destroys the module.
    """
    for relative in changed_files:
        if not relative.endswith(".py"):
            continue
        new_source = (projection / relative).read_text(encoding="utf-8")
        try:
            compile(new_source, relative, "exec")
        except SyntaxError:
            return False

        old_path = Path(workspace) / relative
        if old_path.is_file():
            old_defs = len(_DEF.findall(old_path.read_text(encoding="utf-8")))
            new_defs = len(_DEF.findall(new_source))
            if old_defs > 0 and new_defs == 0:
                return False

    return True


def _apply_projection(projection, workspace, changed_files):
    for relative in changed_files:
        source = projection / relative
        if not source.is_file():
            continue
        destination = Path(workspace) / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def _release_ollama_model(configuration):
    if configuration.provider != "ollama" or configuration.runtime != "host":
        return

    payload = json.dumps({"model": configuration.model, "keep_alive": 0}).encode()
    request = urllib.request.Request(
        "http://127.0.0.1:11434/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15):
            pass
    except (OSError, TimeoutError):
        pass
