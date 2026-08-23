"""Local control surface for the Pithos runner."""

import argparse
import json
from pathlib import Path

from .lock import LockHeld
from .runner import RunnerConfiguration, run_once
from .state import read_state, write_state


def _configuration(arguments) -> RunnerConfiguration:
    return RunnerConfiguration(
        experiment_id=arguments.experiment_id,
        workspace=arguments.workspace.resolve(),
        logs_root=arguments.logs_root.expanduser().resolve(),
        pi_config_dir=arguments.pi_config_dir.resolve(),
        runtime=arguments.runtime,
        docker_image=arguments.docker_image,
        timeout_seconds=arguments.timeout_seconds,
        repeat_limit=arguments.repeat_limit,
        git_socket=arguments.git_socket,
        harness_socket=arguments.harness_socket,
        telegram_socket=arguments.telegram_socket,
        ground_truth_root=arguments.ground_truth_root,
        harness_journals_root=arguments.harness_journals_root,
    )


def main() -> int:
    """Run or control the persistent local runner state."""

    parser = argparse.ArgumentParser(description="Control one Pithos experiment runner")
    parser.add_argument("--logs-root", type=Path, default=Path.home() / "logs" / "pithos")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--experiment-id", required=True)
    run_parser.add_argument("--workspace", type=Path, required=True)
    run_parser.add_argument("--pi-config-dir", type=Path, required=True)
    run_parser.add_argument("--runtime", choices=("docker", "host"), default="docker")
    run_parser.add_argument("--docker-image", default="pithos-agent:local")
    run_parser.add_argument("--timeout-seconds", type=int, default=3600)
    run_parser.add_argument("--repeat-limit", type=int, default=5)
    run_parser.add_argument("--git-socket", type=Path)
    run_parser.add_argument("--harness-socket", type=Path)
    run_parser.add_argument("--telegram-socket", type=Path)
    run_parser.add_argument("--ground-truth-root", type=Path)
    run_parser.add_argument("--harness-journals-root", type=Path)
    subparsers.add_parser("status")
    pause_parser = subparsers.add_parser("pause")
    pause_parser.add_argument("--reason", default="paused by local user")
    subparsers.add_parser("resume")
    arguments = parser.parse_args()
    state_path = arguments.logs_root.expanduser().resolve() / "runtime" / "state.json"

    try:
        if arguments.command == "run":
            result = run_once(_configuration(arguments))
            print(json.dumps(result, indent=2))
            return 0 if result["status"] == "completed" else 1
        if arguments.command == "pause":
            write_state(state_path, True, arguments.reason)
        elif arguments.command == "resume":
            write_state(state_path, False, "resumed by local user")

        print(json.dumps(read_state(state_path), indent=2))
    except (OSError, RuntimeError, LockHeld) as error:
        print(f"Runner error: {error}")

        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
