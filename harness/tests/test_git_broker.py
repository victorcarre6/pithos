import json
import os
import socket
import subprocess
import threading
import uuid
from pathlib import Path

import pytest

from pithos_git_broker.broker import GitBroker
from pithos_git_broker.policy import GitPolicy, PolicyViolation
from pithos_git_broker.server import GitBrokerServer


REMOTE = "https://github.com/example/private-repo"
RUN_ID = "run-20260822T220000Z-a1b2c3"


class FakeCommands:
    def __init__(self):
        self.branch = "agent/rush-feature"
        self.commands = []
        self.pr = {
            "url": "https://github.com/example/private-repo/pull/1",
            "state": "OPEN",
            "headRefName": self.branch,
            "baseRefName": "main",
        }

    def __call__(self, command, cwd):
        self.commands.append(command)
        if command[:4] == ["git", "remote", "get-url", "origin"]:
            stdout = REMOTE + ".git\n"
        elif command[:3] == ["git", "branch", "--show-current"]:
            stdout = self.branch + "\n"
        elif command[:3] == ["git", "show-ref", "--verify"]:
            return subprocess.CompletedProcess(command, 1, "", "")
        elif command[:3] == ["gh", "pr", "view"]:
            stdout = json.dumps(self.pr)
        else:
            stdout = "ok\n"

        return subprocess.CompletedProcess(command, 0, stdout, "")


def _broker(tmp_path):
    repository = tmp_path / "repo"
    repository.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repository, check=True, capture_output=True)
    commands = FakeCommands()
    policy = GitPolicy(repository, REMOTE)

    return GitBroker(policy, tmp_path / "logs", commands), commands


def test_status_is_journaled_without_command_content(tmp_path):
    broker, _ = _broker(tmp_path)

    result = broker.handle({"operation": "status", "arguments": {}, "run_id": RUN_ID})

    assert result["ok"] is True
    events_path = tmp_path / "logs" / "runs" / RUN_ID / "events.jsonl"
    event = json.loads(events_path.read_text())
    assert event["type"] == "git.status"
    assert event["payload"] == {
        "operation": "status",
        "arguments": {},
        "ok": True,
        "exit_code": 0,
        "stdout": "ok\n",
        "stderr": "",
    }

    broker.handle({"operation": "status", "arguments": {}, "run_id": RUN_ID})
    events = [json.loads(line) for line in events_path.read_text().splitlines()]
    assert [event["sequence"] for event in events] == [0, 1]


def test_policy_rejects_unknown_operation_and_branch(tmp_path):
    broker, _ = _broker(tmp_path)

    with pytest.raises(PolicyViolation, match="not allowed"):
        broker.handle({"operation": "repo_create", "arguments": {}, "run_id": RUN_ID})
    with pytest.raises(PolicyViolation, match="namespace"):
        broker.handle(
            {"operation": "switch", "arguments": {"branch": "main"}, "run_id": RUN_ID}
        )


def test_existing_rush_switches_without_recreation(tmp_path):
    broker, commands = _broker(tmp_path)
    original_runner = commands.__call__

    def existing_branch(command, cwd):
        if command[:3] == ["git", "show-ref", "--verify"]:
            return subprocess.CompletedProcess(command, 0, "found\n", "")
        return original_runner(command, cwd)

    broker.command_runner = existing_branch

    broker.handle(
        {
            "operation": "switch",
            "arguments": {"branch": "agent/rush-feature"},
            "run_id": RUN_ID,
        }
    )

    assert ["git", "switch", "agent/rush-feature"] in commands.commands
    assert ["git", "switch", "-c", "agent/rush-feature"] not in commands.commands


def test_new_rush_starts_from_local_main(tmp_path):
    broker, commands = _broker(tmp_path)

    broker.handle(
        {
            "operation": "switch",
            "arguments": {"branch": "agent/rush-new-feature"},
            "run_id": RUN_ID,
        }
    )

    assert ["git", "switch", "-c", "agent/rush-new-feature", "main"] in commands.commands


def test_commit_and_push_never_use_force(tmp_path):
    broker, commands = _broker(tmp_path)

    broker.handle(
        {"operation": "commit", "arguments": {"message": "feat: finish rush"}, "run_id": RUN_ID}
    )
    broker.handle({"operation": "push", "arguments": {}, "run_id": RUN_ID})

    flattened = " ".join(part for command in commands.commands for part in command)
    assert "--force" not in flattened
    assert "TOKEN" not in flattened
    assert ["git", "add", "--all", "--", "."] in commands.commands


def test_completed_rush_can_commit_push_and_create_pr(tmp_path):
    broker, commands = _broker(tmp_path)

    broker.handle(
        {"operation": "commit", "arguments": {"message": "feat: finish rush"}, "run_id": RUN_ID}
    )
    broker.handle({"operation": "push", "arguments": {}, "run_id": RUN_ID})
    broker.handle(
        {
            "operation": "pr_create",
            "arguments": {"title": "Finish rush", "body": "Validated result."},
            "run_id": RUN_ID,
        }
    )

    assert any(command[:3] == ["git", "commit", "-m"] for command in commands.commands)
    assert any(command[:3] == ["git", "push", "--set-upstream"] for command in commands.commands)
    assert any(command[:3] == ["gh", "pr", "create"] for command in commands.commands)


def test_merge_requires_matching_open_pull_request(tmp_path):
    broker, commands = _broker(tmp_path)
    commands.pr["baseRefName"] = "other"

    with pytest.raises(PolicyViolation, match="head/base"):
        broker.handle({"operation": "pr_merge", "arguments": {}, "run_id": RUN_ID})


def test_matching_open_pull_request_can_merge(tmp_path):
    broker, commands = _broker(tmp_path)

    broker.handle({"operation": "pr_merge", "arguments": {}, "run_id": RUN_ID})

    assert any(command[:3] == ["gh", "pr", "merge"] for command in commands.commands)


def test_merge_switches_back_to_main_and_pulls_afterward(tmp_path):
    broker, commands = _broker(tmp_path)

    broker.handle({"operation": "pr_merge", "arguments": {}, "run_id": RUN_ID})

    assert ["git", "switch", "main"] in commands.commands
    assert ["git", "pull", "origin", "main"] in commands.commands
    merge_index = next(i for i, c in enumerate(commands.commands) if c[:3] == ["gh", "pr", "merge"])
    switch_index = commands.commands.index(["git", "switch", "main"])
    assert merge_index < switch_index


def test_a_failed_post_merge_switch_does_not_fail_the_merge(tmp_path):
    broker, commands = _broker(tmp_path)
    original_runner = commands.__call__

    def flaky_switch(command, cwd):
        if command[:2] == ["git", "switch"]:
            return subprocess.CompletedProcess(command, 1, "", "local changes would be overwritten")
        return original_runner(command, cwd)

    broker.command_runner = flaky_switch

    result = broker.handle({"operation": "pr_merge", "arguments": {}, "run_id": RUN_ID})

    assert result["ok"] is True


def test_remote_must_match_policy(tmp_path):
    broker, commands = _broker(tmp_path)

    def wrong_remote(command, cwd):
        if command[:4] == ["git", "remote", "get-url", "origin"]:
            return subprocess.CompletedProcess(command, 0, "https://github.com/other/repo\n", "")
        return commands(command, cwd)

    broker.command_runner = wrong_remote

    with pytest.raises(PolicyViolation, match="not allowed"):
        broker.handle({"operation": "status", "arguments": {}, "run_id": RUN_ID})

    event = json.loads((tmp_path / "logs" / "runs" / RUN_ID / "events.jsonl").read_text())
    assert event["type"] == "git.failed"
    assert event["payload"]["error_type"] == "PolicyViolation"


def test_unix_socket_round_trip_and_permissions(tmp_path):
    broker, _ = _broker(tmp_path)
    socket_path = Path("/private/tmp") / f"pithos-{os.getpid()}-{uuid.uuid4().hex[:8]}.sock"

    with GitBrokerServer(socket_path, broker) as server:
        thread = threading.Thread(target=server.handle_request)
        thread.start()
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.connect(str(socket_path))
            request = {"operation": "status", "arguments": {}, "run_id": RUN_ID}
            client.sendall(json.dumps(request).encode() + b"\n")
            response = json.loads(client.makefile().readline())
        thread.join(timeout=2)

        assert response["ok"] is True
        assert socket_path.stat().st_mode & 0o777 == 0o600
