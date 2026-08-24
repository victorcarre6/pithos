"""CLI for isolated Pi capability scenarios."""

import argparse
import json
from pathlib import Path

from .runner import PiConfiguration, run_scenario
from .scenarios import SCENARIOS


def main() -> int:
    """Run selected scenarios and persist one result per directory."""

    parser = argparse.ArgumentParser(description="Probe Pi capabilities with external effect verification")
    parser.add_argument("scenarios", nargs="*", choices=sorted(SCENARIOS), default=None)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--pi", default="pi")
    parser.add_argument("--provider", default="ollama")
    parser.add_argument("--model", default="qwen3.8:27b")
    parser.add_argument("--timeout-seconds", type=int, default=3600)
    parser.add_argument("--config-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()

    selected_names = list(SCENARIOS) if arguments.all else arguments.scenarios or []
    if not selected_names:
        parser.error("select at least one scenario or pass --all")

    configuration = PiConfiguration(
        executable=arguments.pi,
        provider=arguments.provider,
        model=arguments.model,
        timeout_seconds=arguments.timeout_seconds,
        config_dir=arguments.config_dir,
    )
    results = []
    for name in selected_names:
        result_dir = arguments.output_dir / name
        result = run_scenario(result_dir, SCENARIOS[name], configuration)
        (result_dir / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        results.append(result)
        print(f"{name}: process={result['process_success']} protocol={result['protocol_success']} task={result['task_success']}")

    passed = all(
        result["process_success"] and result["protocol_success"] and result["task_success"]
        for result in results
    )

    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
