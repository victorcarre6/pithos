"""CLI collector for Pithos JSONL event streams."""

import argparse
import json
import time
from pathlib import Path

from .store import EventStore, IngestionError


def _collect(store: EventStore, logs_root: Path) -> list[dict]:
    results = []
    for path in sorted((logs_root / "runs").glob("*/events.jsonl")):
        results.append(store.ingest(path))
    network_log = logs_root / "network" / "access.log"
    if network_log.exists():
        results.append(store.ingest_squid(network_log))

    return results


def main() -> int:
    """Ingest once or poll forever without participating in Pi execution."""

    parser = argparse.ArgumentParser(description="Ingest Pithos JSONL into SQLite")
    parser.add_argument("--logs-root", type=Path, default=Path.home() / "logs" / "pithos")
    parser.add_argument("--database", type=Path)
    parser.add_argument("--interval-seconds", type=float, default=5)
    parser.add_argument("mode", choices=("once", "watch"))
    arguments = parser.parse_args()
    logs_root = arguments.logs_root.expanduser().resolve()
    database = arguments.database or logs_root / "pithos.db"
    store = EventStore(database)

    try:
        while True:
            results = _collect(store, logs_root)
            print(json.dumps(results), flush=True)
            if arguments.mode == "once":
                break
            time.sleep(arguments.interval_seconds)
    except (OSError, IngestionError) as error:
        print(f"Collector error: {error}")
        return 1
    finally:
        store.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
