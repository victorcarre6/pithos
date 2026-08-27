"""Compose context, validation and final evidence for one local mission."""

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from pithos_continuity import publish_report

from .context import ContextSection, build_context
from .controller import ValidationResult
from .state import current_item


class ContextFactory:
    """Build one phase context from durable project facts and targeted files."""

    def __init__(self, workspace, limit=40_000, target_paths=None, project=None):
        self.workspace = Path(workspace)
        self.limit = limit
        self.target_paths = list(target_paths or [])
        self.project = project

    def __call__(self, state):
        brief_path = self.workspace / ".pithos-task.md"
        contract_path = brief_path if brief_path.is_file() else self.workspace / "PROJECT.md"
        contract = contract_path.read_text(encoding="utf-8")
        sections = [ContextSection("Contract", contract, required=True)]
        # `.pithos-task.md`/`PROJECT.md` is a durable, human-authored brief that nothing keeps in sync
        # with the current rush or todo item -- without this, a session can be told to add something
        # that a prior rush already implemented, with no way to notice the contradiction
        if self.project is not None:
            item = current_item(self.project, state)
            task = f"{item['title']}\n\n{item['description']}".strip()
            if task:
                sections.append(ContextSection("Current task", task, required=True))
        if state.failure_summary:
            sections.append(ContextSection("Validation failure", state.failure_summary, required=True))

        target_paths = state.todo[state.todo_index]["target_files"] if state.todo else self.target_paths
        for path in self._target_files(state.changed_files, target_paths):
            relative = path.relative_to(self.workspace)
            content = path.read_text(encoding="utf-8", errors="replace")
            sections.append(ContextSection(f"File: {relative}", content))

        context, _ = build_context(sections, self.limit)

        return context

    def _target_files(self, changed_files, target_paths):
        if target_paths:
            return [
                self.workspace / relative
                for relative in target_paths
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
    """Run the active oracle, then the project regression command when configured."""

    def __init__(self, workspace, command, timeout=120, regression_command=None):
        self.workspace = Path(workspace)
        self.timeout = timeout
        self.command = self._normalized(command)
        self.regression_command = self._normalized(regression_command) if regression_command else None

    def __call__(self, changed_files):
        primary = self._run(self.command)
        if not primary.passed or self.regression_command is None:
            return primary

        regression = self._run(self.regression_command)
        command = f"{primary.command} && {regression.command}"
        stdout = primary.stdout + regression.stdout
        stderr = primary.stderr + regression.stderr

        return ValidationResult(regression.passed, command, stdout, stderr)

    def _run(self, command):
        try:
            result = subprocess.run(
                command,
                cwd=self.workspace,
                capture_output=True,
                text=True,
                check=False,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired as error:
            stdout = error.stdout or ""
            stderr = error.stderr or "validation timed out"

            return ValidationResult(False, " ".join(command), stdout, stderr)

        return ValidationResult(
            result.returncode == 0,
            " ".join(command),
            result.stdout,
            result.stderr,
        )

    @staticmethod
    def _normalized(command):
        normalized = list(command)
        if normalized[0] == "python":
            normalized[0] = sys.executable

        return normalized


class LocalFinalizer:
    """Write and publish a harness-owned continuity report after validation."""

    def __init__(self, workspace, mission_root, logs_root=None, git_send=None, auto_merge=False):
        self.workspace = Path(workspace)
        self.mission_root = Path(mission_root)
        self.logs_root = Path(logs_root) if logs_root else self.mission_root.parent.parent
        self.git_send = git_send
        self.auto_merge = auto_merge

    def __call__(self, state):
        started_at = state.history[0].get("at", state.updated_at) if state.history else state.updated_at
        branch = f"agent/rush-{state.micro_rush_id or state.experiment_id}"
        micro_rush_id = state.micro_rush_id or state.experiment_id
        evidence = "; ".join(
            f"{item['command']}: {'PASS' if item['passed'] else 'FAIL'}"
            for item in state.evidence
        )
        lines = [
            "---",
            'schema_version: "1.0"',
            f"run_id: {state.mission_id}",
            f"experiment_id: {state.experiment_id}",
            f"micro_rush_id: rush-{micro_rush_id}",
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
        micro_rush_id = state.micro_rush_id or state.experiment_id
        self.git_send(
            {
                "operation": "switch",
                "arguments": {"branch": branch},
                "run_id": state.mission_id,
            }
        )

        pull_request = None
        try:
            response = self.git_send(
                {"operation": "pr_view", "arguments": {}, "run_id": state.mission_id}
            )
            pull_request = json.loads(response["stdout"])
        except RuntimeError:
            pass
        if pull_request and pull_request.get("state") != "OPEN":
            state_name = pull_request.get("state", "unknown")
            raise RuntimeError(f"micro-rush pull request is already {state_name}")

        requests = [
            ("commit", {"message": f"feat: complete {micro_rush_id} rush"}),
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

        if pull_request:
            url = pull_request["url"]
        else:
            response = self.git_send(
                {
                    "operation": "pr_create",
                    "arguments": {
                        "title": f"Complete {micro_rush_id} rush",
                        "body": f"Validated by `{state.mission_id}` with the external project oracle.",
                    },
                    "run_id": state.mission_id,
                }
            )
            url = response["stdout"].strip()

        state.artifacts["pull_request"] = url

        if self.auto_merge:
            self._auto_merge(state)

    def _auto_merge(self, state):
        # best-effort: the validated work is already safely committed and pushed above, so a merge
        # hiccup (branch protection, GitHub outage, already-merged race) must not undo that success
        try:
            self.git_send({"operation": "pr_merge", "arguments": {}, "run_id": state.mission_id})
        except RuntimeError as error:
            state.artifacts["merge_failed"] = str(error)
            return

        state.artifacts["merged"] = True
