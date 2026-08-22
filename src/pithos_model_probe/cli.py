"""CLI for the local model probe."""

import argparse
import json
from pathlib import Path

from .client import OllamaClient
from .probe import run_probe


def _write_result(path: Path, result: dict) -> None:
    """Publish a probe checkpoint atomically."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    temporary_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    temporary_path.replace(path)

    completed = len(result["scenarios"])
    last_name = result["scenarios"][-1]["name"] if completed else "startup"
    print(f"Checkpoint {completed}/4 after {last_name}", flush=True)


def main() -> int:
    """Run the probe and store its complete JSON result."""

    parser = argparse.ArgumentParser(description="Probe one model exposed by Ollama")
    parser.add_argument("--model", default="qwen3.8:27b")
    parser.add_argument("--base-url", default="http://127.0.0.1:11434")
    parser.add_argument("--timeout-seconds", type=int, default=600)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()

    client = OllamaClient(arguments.base_url, arguments.timeout_seconds)
    previous_result = None
    if arguments.output.exists():
        decoded_result = json.loads(arguments.output.read_text(encoding="utf-8"))
        if decoded_result.get("model") != arguments.model:
            parser.error("existing output belongs to another model")
        previous_result = decoded_result

    result = run_probe(
        client,
        arguments.model,
        on_progress=lambda checkpoint: _write_result(arguments.output, checkpoint),
        previous_result=previous_result,
    )

    print(f"Probe {'passed' if result['passed'] else 'failed'}: {arguments.output}")

    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
