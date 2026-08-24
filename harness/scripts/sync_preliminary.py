#!/usr/bin/env python3
"""Refresh explicit one-way snapshots from the consolidated harness."""

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


PROJECTS = {
    "00-contracts": {
        "src": ["src/pithos_contracts", "contracts"],
        "tests": ["tests/test_contracts.py"],
    },
    "01-model-benchmark": {
        "src": ["src/pithos_model_probe", "src/pithos_benchmark"],
        "tests": ["tests/test_model_probe.py", "tests/test_pi_configuration.py", "tests/test_benchmark.py"],
    },
    "02-capability-probe": {
        "src": ["src/pithos_capability_probe"],
        "tests": ["tests/test_capability_probe.py"],
    },
    "03-continuity": {
        "src": ["src/pithos_continuity"],
        "tests": ["tests/test_continuity.py"],
    },
    "04-runner": {
        "src": ["src/pithos_runner"],
        "tests": ["tests/test_runner.py", "tests/test_pi_events.py"],
    },
    "05-git-pr": {
        "src": ["src/pithos_git_broker"],
        "tests": ["tests/test_git_broker.py"],
    },
    "06-harness-evolution": {
        "src": ["src/pithos_harness"],
        "tests": ["tests/test_harness.py"],
    },
    "07-event-store": {
        "src": ["src/pithos_event_store"],
        "tests": ["tests/test_event_store.py", "tests/test_observability_integration.py"],
    },
    "08-dashboard": {
        "src": ["dashboard"],
        "tests": ["tests/test_dashboard.py"],
    },
    "09-telegram": {
        "src": ["src/pithos_telegram"],
        "tests": ["tests/test_telegram.py"],
    },
    "10-live-logs": {
        "src": ["src/pithos_live_log"],
        "tests": ["tests/test_live_log.py"],
    },
    "11-campaign-bootstrap": {
        "src": ["scripts/create_experiment.py", "scripts/run_experiment.py", "templates/experiment"],
        "tests": ["tests/test_create_experiment.py", "tests/test_run_experiment.py"],
    },
    "12-weak-model-orchestration": {
        "src": ["src/pithos_orchestrator", "fixtures/visualizer_acceptance.py"],
        "tests": ["tests/test_orchestrator.py"],
    },
}


def sync(harness_root: Path, preliminary_root: Path):
    """Copy declared files and write a hash manifest for every snapshot."""

    manifests = {}
    for project, mapping in PROJECTS.items():
        implementation = preliminary_root / project / "implementation"
        implementation.mkdir(parents=True, exist_ok=True)
        copied = []
        for category, sources in mapping.items():
            for relative_source in sources:
                source = harness_root / relative_source
                destination = implementation / category / Path(relative_source).name
                _copy(source, destination)
                copied.extend(_hashes(destination, implementation))
        manifest = {
            "schema_version": 1,
            "direction": "harness-to-preliminary-snapshot",
            "project": project,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "files": sorted(copied, key=lambda item: item["path"]),
        }
        (implementation / "SNAPSHOT.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        manifests[project] = manifest

    return manifests


def verify(harness_root: Path, preliminary_root: Path):
    """Return source/destination mismatches without changing snapshots."""

    mismatches = []
    for project, mapping in PROJECTS.items():
        implementation = preliminary_root / project / "implementation"
        for category, sources in mapping.items():
            for relative_source in sources:
                source = harness_root / relative_source
                destination = implementation / category / Path(relative_source).name
                source_hashes = _relative_hashes(source)
                destination_hashes = _relative_hashes(destination)
                if source_hashes != destination_hashes:
                    mismatches.append({"project": project, "source": relative_source})

    return mismatches


def _copy(source: Path, destination: Path):
    """Copy one declared file or tree without generated caches."""

    if source.is_dir():
        shutil.copytree(
            source,
            destination,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("__pycache__", "node_modules", "dist", "*.pyc", "*.tsbuildinfo"),
        )
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def _hashes(path: Path, root: Path):
    """Return SHA-256 provenance for copied regular files."""

    files = [path] if path.is_file() else list(path.rglob("*"))

    return [
        {
            "path": str(file.relative_to(root)),
            "sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
        }
        for file in files
        if file.is_file()
    ]


def _relative_hashes(path):
    """Hash one declared source with generated directories excluded."""

    if path.is_file():
        return {path.name: hashlib.sha256(path.read_bytes()).hexdigest()}
    hashes = {}
    for file in path.rglob("*"):
        if not file.is_file():
            continue
        relative = file.relative_to(path)
        if any(part in {"__pycache__", "node_modules", "dist"} for part in relative.parts):
            continue
        if file.suffix == ".pyc" or file.name.endswith(".tsbuildinfo"):
            continue
        hashes[str(relative)] = hashlib.sha256(file.read_bytes()).hexdigest()

    return hashes


def main():
    """Refresh all declared snapshots."""

    parser = argparse.ArgumentParser(description="Refresh preliminary project implementation snapshots")
    parser.add_argument("--harness-root", type=Path, default=Path(__file__).parents[1])
    parser.add_argument("--preliminary-root", type=Path, default=Path(__file__).parents[2] / "preliminary_work")
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    harness_root = arguments.harness_root.resolve()
    preliminary_root = arguments.preliminary_root.resolve()
    if arguments.check:
        mismatches = verify(harness_root, preliminary_root)
        print(json.dumps({"ready": not mismatches, "mismatches": mismatches}, indent=2))

        return 1 if mismatches else 0
    manifests = sync(harness_root, preliminary_root)
    print(json.dumps({"projects": sorted(manifests), "count": len(manifests)}, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
