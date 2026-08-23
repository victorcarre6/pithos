"""Append-only benchmark artifacts, SQLite projection and Git export."""

import json
import shutil
import sqlite3
import threading
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS campaigns (
    campaign_id TEXT PRIMARY KEY,
    model TEXT NOT NULL,
    started_at TEXT NOT NULL,
    status TEXT NOT NULL,
    manifest_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS attempts (
    attempt_id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    scenario_id TEXT NOT NULL,
    attempt_number INTEGER NOT NULL,
    passed INTEGER NOT NULL,
    duration_seconds REAL,
    decode_tokens_per_second REAL,
    result_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS measurements (
    attempt_id TEXT NOT NULL,
    metric TEXT NOT NULL,
    numeric_value REAL,
    text_value TEXT,
    unit TEXT,
    metadata_json TEXT NOT NULL,
    PRIMARY KEY (attempt_id, metric)
);
"""


class BenchmarkStorage:
    """Persist one campaign without making execution depend on SQLite."""

    def __init__(self, logs_root: Path, campaign_id: str):
        self.logs_root = logs_root
        self.campaign_id = campaign_id
        self.campaign_root = logs_root / "benchmarks" / campaign_id
        self.campaign_root.mkdir(parents=True, exist_ok=False)
        self.events_path = self.campaign_root / "events.jsonl"
        self._event_lock = threading.Lock()

    def write_json(self, relative_path, content):
        """Write one immutable structured campaign artifact."""

        path = self.campaign_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raise FileExistsError(path)
        path.write_text(json.dumps(content, indent=2) + "\n", encoding="utf-8")

        return path

    def event(self, event):
        """Append and flush one benchmark event."""

        line = json.dumps(event, separators=(",", ":"))
        with self._event_lock:
            with self.events_path.open("a", encoding="utf-8") as stream:
                stream.write(line + "\n")
                stream.flush()

    def append_json(self, relative_path, content):
        """Append one immediately flushed JSONL artifact."""

        path = self.campaign_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(content, separators=(",", ":"))
        with path.open("a", encoding="utf-8") as stream:
            stream.write(line + "\n")
            stream.flush()

        return path

    def project(self):
        """Rebuild the campaign SQLite projection from result artifacts."""

        database = self.campaign_root / "benchmark.db"
        connection = sqlite3.connect(database)
        connection.executescript(SCHEMA)
        manifest = json.loads((self.campaign_root / "manifest.json").read_text(encoding="utf-8"))
        connection.execute(
            "INSERT OR REPLACE INTO campaigns VALUES (?, ?, ?, ?, ?)",
            (
                self.campaign_id,
                manifest["model"],
                manifest["started_at"],
                manifest["status"],
                json.dumps(manifest),
            ),
        )

        for path in sorted(self.campaign_root.glob("attempts/*/*/result.json")):
            result = json.loads(path.read_text(encoding="utf-8"))
            connection.execute(
                "INSERT OR REPLACE INTO attempts VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    result["attempt_id"],
                    self.campaign_id,
                    result["scenario_id"],
                    result["attempt_number"],
                    int(result["passed"]),
                    result.get("duration_seconds"),
                    result.get("decode_tokens_per_second"),
                    json.dumps(result),
                ),
            )
            for metric, value in result.get("measurements", {}).items():
                numeric = value if isinstance(value, (int, float)) else None
                text = None if numeric is not None else str(value)
                connection.execute(
                    "INSERT OR REPLACE INTO measurements VALUES (?, ?, ?, ?, ?, ?)",
                    (result["attempt_id"], metric, numeric, text, None, "{}"),
                )

        connection.commit()
        connection.close()

    def export(self, results_root: Path):
        """Copy the complete versionable campaign beside the benchmark source."""

        destination = results_root / self.campaign_id
        if destination.exists():
            raise FileExistsError(destination)
        shutil.copytree(
            self.campaign_root,
            destination,
            ignore=shutil.ignore_patterns("benchmark.db", "*.db-shm", "*.db-wal"),
        )
        self._update_results_index(results_root.parent)

        return destination

    def _update_results_index(self, results_root):
        """Publish the versioned campaign index atomically."""

        index_path = results_root / "index.json"
        if index_path.is_file():
            index = json.loads(index_path.read_text(encoding="utf-8"))
        else:
            index = {"schema_version": 1, "campaigns": [], "legacy": []}
        manifest = json.loads((self.campaign_root / "manifest.json").read_text(encoding="utf-8"))
        campaigns = [item for item in index["campaigns"] if item["campaign_id"] != self.campaign_id]
        campaigns.append(
            {
                "campaign_id": self.campaign_id,
                "model": manifest["model"],
                "suite": manifest["suite"],
                "status": manifest["status"],
                "path": f"campaigns/{self.campaign_id}",
                "summary": manifest["summary"],
            }
        )
        index["campaigns"] = sorted(campaigns, key=lambda item: item["campaign_id"])
        temporary = index_path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
        temporary.replace(index_path)
