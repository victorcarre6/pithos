#!/usr/bin/env python3
"""Run one local multi-session Ling mission with external validation."""

import argparse
import json
from pathlib import Path

from pithos_orchestrator.launcher import launch


def main():
    parser = argparse.ArgumentParser(description="Run one multi-session Pithos mission")
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--logs-root", type=Path, default=Path.home() / "logs" / "pithos")
    parser.add_argument("--git-socket", type=Path)
    parser.add_argument("--telegram-socket", type=Path)
    arguments = parser.parse_args()
    result = launch(
        arguments.workspace,
        arguments.logs_root,
        arguments.git_socket,
        arguments.telegram_socket,
    )
    print(json.dumps(result.__dict__, indent=2))

    return 0 if result.status == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
