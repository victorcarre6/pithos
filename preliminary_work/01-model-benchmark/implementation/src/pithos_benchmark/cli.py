"""Command-line entry point for benchmark campaigns and consultation."""

import argparse
import json
from pathlib import Path

from .engine import BenchmarkConfiguration, BenchmarkEngine
from .ollama import OllamaClient


PACKAGE_ROOT = Path(__file__).resolve().parent
HARNESS_ROOT = PACKAGE_ROOT.parents[1]
REPOSITORY_ROOT = HARNESS_ROOT.parent
DEFAULT_SCENARIOS = PACKAGE_ROOT / "scenario_data"
DEFAULT_RESULTS = REPOSITORY_ROOT / "preliminary_work" / "01-model-benchmark" / "results" / "campaigns"


def _run(arguments):
    """Build a configuration and run with or without the TUI."""

    results_root = arguments.results_root
    if results_root is None and DEFAULT_RESULTS.parent.parent.is_dir():
        results_root = DEFAULT_RESULTS
    configuration = BenchmarkConfiguration(
        model=arguments.model,
        logs_root=arguments.logs_root.expanduser().resolve(),
        scenarios_root=arguments.scenarios_root.resolve(),
        results_root=results_root.resolve() if results_root else None,
        suite=arguments.suite,
        attempts=arguments.attempts,
        minimum_tokens_per_second=arguments.minimum_tokens_per_second,
        ollama_url=arguments.ollama_url,
        pi_config_dir=arguments.pi_config_dir.resolve(),
        pi_executable=arguments.pi,
        timeout_override_seconds=arguments.timeout_seconds,
    )
    if arguments.no_tui:
        engine = BenchmarkEngine(configuration, on_event=_print_event)
        manifest = engine.run()
        print(json.dumps(manifest, indent=2))

        return 0

    from .tui import BenchmarkApp

    engine = BenchmarkEngine(configuration)
    BenchmarkApp(engine).run()

    return 0


def _print_event(event):
    """Render one compact line for headless automation."""

    timestamp = event["timestamp"][11:19]
    print(f"{timestamp} {event['type']} {json.dumps(event['payload'], separators=(',', ':'))}", flush=True)


def _list_models(arguments):
    """Print installed and resident Ollama models."""

    client = OllamaClient(arguments.ollama_url)
    running = {item.get("name") or item.get("model") for item in client.running_models()}
    for model in client.models():
        name = model.get("name") or model.get("model")
        state = "resident" if name in running else "idle"
        size = model.get("size", 0)
        print(f"{name:<32} {state:<9} {size / 1_000_000_000:>6.1f} GB")

    return 0


def _dashboard(arguments):
    """Serve the read-only benchmark dashboard on localhost."""

    import uvicorn

    from .dashboard import create_app

    results_root = arguments.results_root or DEFAULT_RESULTS
    app = create_app(arguments.logs_root, results_root)
    uvicorn.run(app, host="127.0.0.1", port=arguments.port)

    return 0


def main():
    """Parse the compact benchmark command surface."""

    parser = argparse.ArgumentParser(description="Benchmark one local Ollama model through Ollama and Pi")
    parser.add_argument("model", nargs="?", help="installed Ollama model name, or list/dashboard")
    parser.add_argument(
        "--suite",
        choices=("smoke", "protocol", "pi", "agentic", "endurance", "context", "full"),
        default="full",
    )
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--minimum-tokens-per-second", type=float, default=0.05)
    parser.add_argument("--timeout-seconds", type=int)
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--logs-root", type=Path, default=Path.home() / "logs" / "pithos")
    parser.add_argument("--results-root", type=Path)
    parser.add_argument("--scenarios-root", type=Path, default=DEFAULT_SCENARIOS)
    parser.add_argument("--pi-config-dir", type=Path, default=HARNESS_ROOT / "config" / "pi")
    parser.add_argument("--pi", default="pi")
    parser.add_argument("--no-tui", action="store_true")
    parser.add_argument("--port", type=int, default=4311)
    arguments = parser.parse_args()

    if arguments.model == "list":
        return _list_models(arguments)
    if arguments.model == "dashboard":
        return _dashboard(arguments)
    if not arguments.model:
        parser.error("provide an installed model name, list, or dashboard")
    if arguments.attempts < 1:
        parser.error("--attempts must be positive")

    return _run(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
