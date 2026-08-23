"""Validate repository, branches and operations before any Git mutation."""

import re
from dataclasses import dataclass
from pathlib import Path


BRANCH_PATTERN = re.compile(r"^agent/rush-[a-z0-9][a-z0-9-]{0,63}$")
COMMIT_PATTERN = re.compile(r"^[^\n]{1,120}$")


class PolicyViolation(ValueError):
    """Reject an operation outside the configured repository policy."""


@dataclass(frozen=True)
class GitPolicy:
    """Immutable allowlist used by the host broker."""

    repository: Path
    remote_url: str
    main_branch: str = "main"

    def validate_repository(self) -> Path:
        resolved = self.repository.resolve()
        if not (resolved / ".git").exists():
            raise PolicyViolation(f"not a Git repository: {resolved}")

        return resolved

    def validate_branch(self, branch: str) -> str:
        if not BRANCH_PATTERN.fullmatch(branch):
            raise PolicyViolation(f"branch is outside agent namespace: {branch}")

        return branch

    def validate_commit_message(self, message: str) -> str:
        if not COMMIT_PATTERN.fullmatch(message):
            raise PolicyViolation("commit message must be one line and at most 120 characters")

        return message

