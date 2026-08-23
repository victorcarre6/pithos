"""Read-only HTTP API over the Pithos SQLite projection."""

import json
import os
import re
import sqlite3
from contextlib import closing
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query


DATABASE_PATH = Path(os.getenv("PITHOS_DATABASE", "/logs/pithos.db"))
LOGS_ROOT = Path(os.getenv("PITHOS_LOGS_ROOT", "/logs"))
app = FastAPI(title="Pithos observability", version="1.0.0")
RUN_ID_PATTERN = re.compile(r"^run-[0-9]{8}T[0-9]{6}Z-[a-z0-9]{6}$")
ARTIFACTS = {"report.md", "run.json", "stdout.jsonl", "stderr.log", "events.jsonl"}


def _connect():
    """Open SQLite in immutable application-level read-only mode."""

    if not DATABASE_PATH.is_file():
        raise HTTPException(503, "Pithos database unavailable")

    uri = f"file:{DATABASE_PATH.resolve()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row

    return connection


def _rows(query, parameters=()):
    with closing(_connect()) as connection:
        rows = connection.execute(query, parameters).fetchall()

    return [dict(row) for row in rows]


@app.get("/api/health")
def health():
    """Distinguish a live API from an available projection."""

    if not DATABASE_PATH.is_file():
        return {"service": "available", "data": "unavailable", "database": str(DATABASE_PATH)}

    try:
        events = _rows("SELECT count(*) AS count FROM events")[0]["count"]
    except sqlite3.Error as error:
        return {"service": "available", "data": "invalid", "error": str(error)}

    return {"service": "available", "data": "available", "events": events}


@app.get("/api/stats")
def stats():
    """Return bounded aggregate counters for the overview."""

    query = """
        SELECT
            count(*) AS total_runs,
            coalesce(sum(status = 'running'), 0) AS running_runs,
            coalesce(sum(status = 'completed'), 0) AS completed_runs,
            coalesce(sum(status NOT IN ('running', 'completed')), 0) AS other_runs
        FROM runs
    """
    counters = _rows(query)[0]
    counters["events"] = _rows("SELECT count(*) AS count FROM events")[0]["count"]
    counters["tool_failures"] = _rows(
        "SELECT count(*) AS count FROM tool_calls WHERE is_error = 1"
    )[0]["count"]
    totals = _rows(
        """
        SELECT coalesce(sum(total_tokens), 0) AS total_tokens,
               coalesce(sum(duration_ms), 0) AS duration_ms
        FROM runs
        """
    )[0]
    counters.update(totals)

    return counters


@app.get("/api/runs")
def runs(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
    """List runs without loading their event payloads."""

    items = _rows(
        "SELECT * FROM runs ORDER BY started_at DESC LIMIT ? OFFSET ?",
        (limit, offset),
    )

    return {"items": items, "limit": limit, "offset": offset}


@app.get("/api/runs/{run_id}")
def run(run_id: str):
    items = _rows("SELECT * FROM runs WHERE run_id = ?", (run_id,))
    if not items:
        raise HTTPException(404, "Run not found")

    return items[0]


@app.get("/api/runs/{run_id}/events")
def events(
    run_id: str,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    event_type: str | None = None,
    domain: str | None = None,
):
    """Page raw events so large runs never load as one response."""

    parameters = [run_id]
    predicate = "run_id = ?"
    if event_type:
        predicate += " AND type = ?"
        parameters.append(event_type)
    if domain:
        predicate += " AND type LIKE ?"
        parameters.append(f"{domain}.%")
    parameters.extend([limit, offset])
    query = f"""
        SELECT event_id, timestamp, type, source, sequence, payload_json
        FROM events WHERE {predicate}
        ORDER BY sequence, timestamp LIMIT ? OFFSET ?
    """
    items = _rows(query, parameters)
    for item in items:
        item["payload"] = json.loads(item.pop("payload_json"))

    return {"items": items, "limit": limit, "offset": offset}


@app.get("/api/runs/{run_id}/report")
def report(run_id: str):
    """Read only the report belonging to the exact validated run directory."""

    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise HTTPException(400, "Invalid run id")

    report_path = (LOGS_ROOT / "runs" / run_id / "report.md").resolve()
    expected_parent = (LOGS_ROOT / "runs" / run_id).resolve()
    if report_path.parent != expected_parent or not report_path.is_file():
        raise HTTPException(404, "Report not found")

    return {"content": report_path.read_text(encoding="utf-8")}


@app.get("/api/runs/{run_id}/artifacts/{name}")
def artifact(
    run_id: str,
    name: str,
    offset: int = Query(0, ge=0),
    limit_bytes: int = Query(64_000, ge=1, le=256_000),
):
    """Page an allowlisted raw artifact without loading the full file."""

    if not RUN_ID_PATTERN.fullmatch(run_id) or name not in ARTIFACTS:
        raise HTTPException(400, "Invalid artifact path")
    path = LOGS_ROOT / "runs" / run_id / name
    if not path.is_file():
        raise HTTPException(404, "Artifact not found")

    with path.open("rb") as artifact_file:
        artifact_file.seek(offset)
        content = artifact_file.read(limit_bytes)
        next_offset = artifact_file.tell()
    size = path.stat().st_size

    return {
        "name": name,
        "content": content.decode("utf-8", errors="replace"),
        "offset": offset,
        "next_offset": next_offset,
        "has_more": next_offset < size,
        "size": size,
    }
