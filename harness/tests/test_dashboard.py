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


def test_artifacts_are_allowlisted_and_byte_paginated(tmp_path):
    client, _ = _client(tmp_path)
    run_dir = tmp_path / "runs" / "run-20260823T120000Z-a1b2c3"
    run_dir.mkdir(parents=True)
    (run_dir / "stdout.jsonl").write_text("0123456789")

    page = client.get(
        "/api/runs/run-20260823T120000Z-a1b2c3/artifacts/stdout.jsonl?limit_bytes=4"
    ).json()
    rejected = client.get(
        "/api/runs/run-20260823T120000Z-a1b2c3/artifacts/secret.env"
    )

    assert page["content"] == "0123"
    assert page["next_offset"] == 4
    assert page["has_more"] is True
    assert rejected.status_code == 400


def test_read_only_api_sees_uncheckpointed_wal_data(tmp_path):
    client, database = _client(tmp_path)
    writer = sqlite3.connect(database)
    writer.execute("PRAGMA journal_mode=WAL")
    writer.execute("PRAGMA wal_autocheckpoint=0")
    writer.execute(
        """
        INSERT INTO runs(run_id, status, started_at)
        VALUES ('run-20260823T130000Z-d4e5f6', 'running', '2026-08-23T13:00:00Z')
        """
    )
    writer.commit()

    runs = client.get("/api/runs").json()["items"]

    assert {run["run_id"] for run in runs} == {
        "run-20260823T120000Z-a1b2c3",
        "run-20260823T130000Z-d4e5f6",
    }
    writer.close()
