"""Execute the small Git/GitHub operation set exposed by the broker."""

import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from pithos_runner.events import EventWriter

from .policy import GitPolicy, PolicyViolation


CommandRunner = Callable[[list[str], Path], subprocess.CompletedProcess]
RUN_ID_PATTERN = re.compile(r"^run-[0-9]{8}T[0-9]{6}Z-[a-z0-9]{6}$")


def _default_runner(command: list[str], cwd: Path) -> subprocess.CompletedProcess:
    environment = {
        "HOME": os.environ.get("HOME", ""),
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "GH_CONFIG_DIR": os.environ.get("GH_CONFIG_DIR", ""),
        "GIT_TERMINAL_PROMPT": "0",
    }

    return subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )


@dataclass
class GitBroker:
    """Handle allowlisted requests and journal their sanitized results."""

    policy: GitPolicy
    logs_root: Path
    command_runner: CommandRunner = _default_runner

    def _run(self, command: list[str]) -> dict:
        repository = self.policy.validate_repository()
        result = self.command_runner(command, repository)
        response = {
            "ok": result.returncode == 0,
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
        if result.returncode != 0:
            raise RuntimeError(json.dumps(response))

        return response

    def _current_branch(self) -> str:
        response = self._run(["git", "branch", "--show-current"])
        branch = response["stdout"].strip()

        return self.policy.validate_branch(branch)

    def handle(self, request: dict) -> dict:
        """Validate and execute one broker request."""

        operation = request.get("operation")
        arguments = request.get("arguments") or {}
        run_id = request.get("run_id")
        if not isinstance(run_id, str) or not RUN_ID_PATTERN.fullmatch(run_id):
            raise PolicyViolation("run_id is required")

        handlers = {
            "status": self._status,
            "switch": self._switch,
            "commit": self._commit,
            "push": self._push,
            "pr_create": self._pr_create,
            "pr_view": self._pr_view,
            "pr_merge": self._pr_merge,
        }
        if operation not in handlers:
            raise PolicyViolation(f"operation is not allowed: {operation}")

        try:
            self._validate_remote()
            response = handlers[operation](arguments)
        except (RuntimeError, PolicyViolation, subprocess.SubprocessError) as error:
            self._journal(
                run_id,
                "failed",
                {
                    "operation": operation,
                    "arguments": arguments,
                    "ok": False,
                    "error_type": type(error).__name__,
                },
            )
            raise

        event_payload = {
            "operation": operation,
            "arguments": arguments,
            "ok": response["ok"],
            "exit_code": response["exit_code"],
            "stdout": response["stdout"],
            "stderr": response["stderr"],
        }
        if operation == "pr_create" and response["ok"]:
            event_payload["url"] = response["stdout"].strip()
        elif operation == "pr_view" and response["ok"]:
            event_payload["pull_request"] = json.loads(response["stdout"])
        self._journal(run_id, operation, event_payload)

        return response

    def _journal(self, run_id: str, action: str, payload: dict) -> None:
        events_path = self.logs_root / "runs" / run_id / "events.jsonl"
        EventWriter(events_path, run_id, source="git-broker").append(f"git.{action}", payload)

    def _validate_remote(self) -> None:
        repository = self.policy.validate_repository()
        result = self.command_runner(["git", "remote", "get-url", "origin"], repository)
        if result.returncode != 0:
            raise PolicyViolation("origin remote is unavailable")
        configured = result.stdout.strip().removesuffix(".git")
        allowed = self.policy.remote_url.strip().removesuffix(".git")
        if configured != allowed:
            raise PolicyViolation(f"origin remote is not allowed: {configured}")

    def _status(self, arguments: dict) -> dict:
        if arguments:
            raise PolicyViolation("status accepts no arguments")

        return self._run(["git", "status", "--short", "--branch", "--", "."])

    def _switch(self, arguments: dict) -> dict:
        branch = self.policy.validate_branch(arguments.get("branch", ""))
        existing = self.command_runner(["git", "show-ref", "--verify", f"refs/heads/{branch}"], self.policy.repository)
        if existing.returncode == 0:
            return self._run(["git", "switch", branch])

        return self._run(["git", "switch", "-c", branch])

    def _commit(self, arguments: dict) -> dict:
        self._current_branch()
        message = self.policy.validate_commit_message(arguments.get("message", ""))
        self._run(["git", "add", "--all", "--", "."])

        return self._run(["git", "commit", "-m", message])

    def _push(self, arguments: dict) -> dict:
        if arguments:
            raise PolicyViolation("push accepts no arguments")
        branch = self._current_branch()

        return self._run(["git", "push", "--set-upstream", "origin", branch])

    def _pr_create(self, arguments: dict) -> dict:
        branch = self._current_branch()
        title = arguments.get("title", "")
        body = arguments.get("body", "")
        if not isinstance(title, str) or not title.strip() or "\n" in title:
            raise PolicyViolation("PR title must be one non-empty line")
        if not isinstance(body, str):
            raise PolicyViolation("PR body must be text")

        return self._run(
            [
                "gh",
                "pr",
                "create",
                "--repo",
                self.policy.remote_url,
                "--base",
                self.policy.main_branch,
                "--head",
                branch,
                "--title",
                title,
                "--body",
                body,
            ]
        )

    def _pr_view(self, arguments: dict) -> dict:
        if arguments:
            raise PolicyViolation("pr_view accepts no arguments")
        branch = self._current_branch()

        return self._run(
            ["gh", "pr", "view", branch, "--repo", self.policy.remote_url, "--json", "url,state,headRefName,baseRefName"]
        )

    def _pr_merge(self, arguments: dict) -> dict:
        if arguments:
            raise PolicyViolation("pr_merge accepts no arguments")
        branch = self._current_branch()
        view = self._pr_view({})
        metadata = json.loads(view["stdout"])
        if metadata.get("headRefName") != branch or metadata.get("baseRefName") != self.policy.main_branch:
            raise PolicyViolation("PR head/base do not match the allowed branch policy")
        if metadata.get("state") != "OPEN":
            raise PolicyViolation("only an open PR can be merged")

        return self._run(
            ["gh", "pr", "merge", branch, "--repo", self.policy.remote_url, "--merge", "--delete-branch"]
        )
