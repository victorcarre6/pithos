"""Compose context, validation and final evidence for one local mission."""

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from pithos_continuity import publish_report

from .context import ContextSection, build_context
from .controller import ValidationResult


class ContextFactory:
    """Build one phase context from durable project facts and targeted files."""

    def __init__(self, workspace, limit=40_000, target_paths=None):
        self.workspace = Path(workspace)
        self.limit = limit
        self.target_paths = list(target_paths or [])

    def __call__(self, state):
        brief_path = self.workspace / ".pithos-task.md"
        contract_path = brief_path if brief_path.is_file() else self.workspace / "PROJECT.md"
        contract = contract_path.read_text(encoding="utf-8")
        sections = [ContextSection("Contract", contract, required=True)]
        if state.failure_summary:
            sections.append(ContextSection("Validation failure", state.failure_summary, required=True))

        for path in self._target_files(state.changed_files):
            relative = path.relative_to(self.workspace)
            content = path.read_text(encoding="utf-8", errors="replace")
            sections.append(ContextSection(f"File: {relative}", content))

        context, _ = build_context(sections, self.limit)

        return context

    def _target_files(self, changed_files):
        if self.target_paths:
            return [
                self.workspace / relative
                for relative in self.target_paths
                if (self.workspace / relative).is_file()
            ]

        candidates = []
        code_suffixes = {".py", ".js", ".ts", ".tsx", ".jsx"}
        for relative in changed_files:
            path = self.workspace / relative
            name = path.name.lower()
            is_test = name.startswith("test_") or "_test" in name or "tests" in name
            eligible = path.is_file() and path.suffix in code_suffixes
            if eligible and not is_test and ".pithos" not in path.parts:
                candidates.append(path)
        patterns = ("src/**/*.py", "tests/**/*.py", "src/**/*.js", "tests/**/*.js")
        for pattern in patterns:
            for path in sorted(self.workspace.glob(pattern)):
                name = path.name.lower()
                if name.startswith("test_") or "_test" in name or "tests" in name:
                    continue
                if path not in candidates:
                    candidates.append(path)

        return candidates[:6]


class CommandValidator:
    """Run the project-owned validation command outside the model session."""

    def __init__(self, workspace, command, timeout=120):
        self.workspace = Path(workspace)
        self.command = list(command)
        self.timeout = timeout

    def __call__(self, changed_files):
        try:
            result = subprocess.run(
                self.command,
                cwd=self.workspace,
                capture_output=True,
                text=True,
                check=False,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired as error:
            stdout = error.stdout or ""
            stderr = error.stderr or "validation timed out"

            return ValidationResult(False, " ".join(self.command), stdout, stderr)

        return ValidationResult(
            result.returncode == 0,
            " ".join(self.command),
            result.stdout,
            result.stderr,
        )


class LocalFinalizer:
    """Write and publish a harness-owned continuity report after validation."""

    def __init__(self, workspace, mission_root, logs_root=None, git_send=None):
        self.workspace = Path(workspace)
        self.mission_root = Path(mission_root)
        self.logs_root = Path(logs_root) if logs_root else self.mission_root.parent.parent
        self.git_send = git_send

    def __call__(self, state):
        started_at = state.history[0].get("at", state.updated_at) if state.history else state.updated_at
        branch = f"agent/rush-{state.experiment_id}"
        evidence = "; ".join(
            f"{item['command']}: {'PASS' if item['passed'] else 'FAIL'}"
            for item in state.evidence
        )
        lines = [
            "---",
            'schema_version: "1.0"',
            f"run_id: {state.mission_id}",
            f"experiment_id: {state.experiment_id}",
            f"micro_rush_id: rush-{state.experiment_id}",
            "status: completed",
            f'started_at: "{started_at}"',
            f'finished_at: "{datetime.now(timezone.utc).isoformat()}"',
            f"branch: {branch if self.git_send else 'null'}",
            "commit_before: null",
            "commit_after: null",
            "stop_reason: null",
            "next_wake: local_resume",
            "---",
            "",
            "## Context",
            "",
            f"Mission `{state.mission_id}` for `{state.experiment_id}`.",
            "",
            "## Work",
            "",
            f"Changed files: {', '.join(state.changed_files) or 'none'}.",
            f"Validation: {evidence}.",
            f"Repairs: {state.repair_attempts}.",
            "",
            "## Next items",
            "",
            "- Continue from the verified workspace state.",
        ]
        report = "\n".join(lines) + "\n"
        workspace_report = self.workspace / ".pithos" / "report.md"
        workspace_report.parent.mkdir(parents=True, exist_ok=True)
        workspace_report.write_text(report, encoding="utf-8")
        self.mission_root.mkdir(parents=True, exist_ok=True)
        (self.mission_root / "report.md").write_text(report, encoding="utf-8")

        if self.git_send:
            self._finalize_git(state, branch)

        archive = publish_report(workspace_report, self.logs_root)
        state.artifacts["continuity_report"] = str(archive)

    def _finalize_git(self, state, branch):
        requests = [
            ("switch", {"branch": branch}),
            ("commit", {"message": f"feat: complete {state.experiment_id} rush"}),
            ("push", {}),
        ]
        for operation, arguments in requests:
            self.git_send(
                {
                    "operation": operation,
                    "arguments": arguments,
                    "run_id": state.mission_id,
                }
            )

        try:
            response = self.git_send(
                {"operation": "pr_view", "arguments": {}, "run_id": state.mission_id}
            )
            pull_request = json.loads(response["stdout"])
            url = pull_request["url"]
        except RuntimeError:
            response = self.git_send(
                {
                    "operation": "pr_create",
                    "arguments": {
                        "title": f"Complete {state.experiment_id} rush",
                        "body": f"Validated by `{state.mission_id}` with the external project oracle.",
                    },
                    "run_id": state.mission_id,
                }
            )
            url = response["stdout"].strip()

        state.artifacts["pull_request"] = url
