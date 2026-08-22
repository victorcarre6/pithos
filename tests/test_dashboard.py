import importlib.util
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from pithos_event_store.migrations import migrate


APP_PATH = Path(__file__).parents[1] / "dashboard" / "api" / "app.py"


def _client(tmp_path):
    database = tmp_path / "pithos.db"
    connection = sqlite3.connect(database)
    migrate(connection)
    connection.execute(
        """
        INSERT INTO runs(run_id, model, status, started_at)
        VALUES ('run-20260823T120000Z-a1b2c3', 'qwen', 'running', '2026-08-23T12:00:00Z')
        """
    )
    connection.execute(
        """
        INSERT INTO events VALUES (
            'evt-20260823T120000.000000Z-a1b2c3',
            'run-20260823T120000Z-a1b2c3', '2026-08-23T12:00:00Z',
            'run.started', 'runner', 0, '{"model":"qwen"}', '{"raw":true}',
            '/logs/events.jsonl', 1
        )
        """
    )
    connection.commit()
    connection.close()

    spec = importlib.util.spec_from_file_location("pithos_dashboard_app", APP_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.DATABASE_PATH = database
    module.LOGS_ROOT = tmp_path

    return TestClient(module.app), database


def test_dashboard_reads_paginated_projection_without_writing(tmp_path):
    client, database = _client(tmp_path)
    before = database.read_bytes()

    health = client.get("/api/health").json()
    runs = client.get("/api/runs?limit=1&offset=0").json()
    events = client.get(
        "/api/runs/run-20260823T120000Z-a1b2c3/events?limit=1&offset=0"
    ).json()

    assert health == {"service": "available", "data": "available", "events": 1}
    assert runs["items"][0]["model"] == "qwen"
    assert events["items"][0]["payload"] == {"model": "qwen"}
    assert database.read_bytes() == before


def test_health_distinguishes_missing_data(tmp_path):
    client, _ = _client(tmp_path)
    missing = tmp_path / "missing.db"
    client.app.routes[0]

    # module global is resolved from the endpoint globals
    health_endpoint = next(route.endpoint for route in client.app.routes if route.path == "/api/health")
    health_endpoint.__globals__["DATABASE_PATH"] = missing

    assert client.get("/api/health").json()["data"] == "unavailable"


def test_report_rejects_path_traversal(tmp_path):
    client, _ = _client(tmp_path)

    response = client.get("/api/runs/not-a-run/report")

    assert response.status_code == 400
