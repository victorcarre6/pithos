"""CLI for explicit harness lifecycle operations."""

import argparse
import json
from pathlib import Path

from .manager import HarnessError, HarnessManager
from .broker import HarnessBroker
from .server import HarnessBrokerServer
from .validation import ResourceValidationError


def main() -> int:
    """Snapshot, promote, audit or restore one harness resource."""

    parser = argparse.ArgumentParser(description="Manage Pithos harness evolution")
    parser.add_argument("--active-root", type=Path, required=True)
    parser.add_argument("--ground-truth-root", type=Path, required=True)
    parser.add_argument("--journals-root", type=Path, required=True)
    parser.add_argument("--logs-root", type=Path)
    subparsers = parser.add_subparsers(dest="command", required=True)

    begin = subparsers.add_parser("begin")
    begin.add_argument("run_id")
    promote = subparsers.add_parser("promote")
    promote.add_argument("run_id")
    promote.add_argument("kind", choices=("skill", "extension", "prompt", "instructions"))
    promote.add_argument("staged", type=Path)
    promote.add_argument("target", type=Path)
    finish = subparsers.add_parser("finish")
    finish.add_argument("run_id")
    finish.add_argument("--rationale", required=True)
    finish.add_argument("--validation", required=True)
    restore = subparsers.add_parser("restore")
    restore.add_argument("path", type=Path)
    subparsers.add_parser("diff")
    serve = subparsers.add_parser("serve")
    serve.add_argument("--socket", type=Path, required=True)
    arguments = parser.parse_args()
    manager = HarnessManager(
        arguments.active_root,
        arguments.ground_truth_root,
        arguments.journals_root,
        arguments.logs_root,
    )

    try:
        if arguments.command == "begin":
            result = str(manager.begin(arguments.run_id))
        elif arguments.command == "promote":
            result = str(manager.promote(arguments.run_id, arguments.staged, arguments.target, arguments.kind))
        elif arguments.command == "finish":
            result = manager.finish(arguments.run_id, arguments.rationale, arguments.validation)
        elif arguments.command == "restore":
            result = str(manager.restore(arguments.path))
        elif arguments.command == "serve":
            broker = HarnessBroker(manager)
            with HarnessBrokerServer(arguments.socket, broker) as server:
                print(f"Harness broker listening on {arguments.socket}", flush=True)
                server.serve_forever()
            return 0
        else:
            result = manager.diff_ground_truth()
    except (OSError, HarnessError, ResourceValidationError) as error:
        print(f"Harness error: {error}")

        return 1

    print(json.dumps(result, indent=2) if isinstance(result, dict) else result)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
