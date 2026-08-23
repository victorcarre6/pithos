"""Start the host-side Git broker."""

import argparse
from pathlib import Path

from .broker import GitBroker
from .policy import GitPolicy
from .server import GitBrokerServer


def main() -> int:
    """Serve the configured repository policy over a mode-0600 Unix socket."""

    parser = argparse.ArgumentParser(description="Run the Pithos Git broker")
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--remote", required=True)
    parser.add_argument("--main-branch", default="main")
    parser.add_argument("--socket", type=Path, required=True)
    parser.add_argument("--logs-root", type=Path, default=Path.home() / "logs" / "pithos")
    arguments = parser.parse_args()

    policy = GitPolicy(arguments.repository, arguments.remote, arguments.main_branch)
    broker = GitBroker(policy, arguments.logs_root.expanduser())

    with GitBrokerServer(arguments.socket, broker) as server:
        print(f"Git broker listening on {arguments.socket}", flush=True)
        server.serve_forever()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

