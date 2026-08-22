"""Ordered SQLite migrations for the Pithos event projection."""


MIGRATIONS = [
    """
    CREATE TABLE events (
        event_id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        type TEXT NOT NULL,
        source TEXT NOT NULL,
        sequence INTEGER,
        payload_json TEXT NOT NULL,
        raw_json TEXT NOT NULL,
        file_path TEXT NOT NULL,
        line_number INTEGER NOT NULL,
        UNIQUE(file_path, line_number)
    );
    CREATE INDEX events_run_timestamp ON events(run_id, timestamp);
    CREATE INDEX events_type_timestamp ON events(type, timestamp);

    CREATE TABLE ingestion_sources (
        file_path TEXT PRIMARY KEY,
        offset_bytes INTEGER NOT NULL,
        line_number INTEGER NOT NULL,
        updated_at TEXT NOT NULL
    );

    CREATE TABLE quarantine (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_path TEXT NOT NULL,
        line_number INTEGER NOT NULL,
        raw_content TEXT NOT NULL,
        error TEXT NOT NULL,
        quarantined_at TEXT NOT NULL,
        UNIQUE(file_path, line_number)
    );

    CREATE TABLE runs (
        run_id TEXT PRIMARY KEY,
        experiment_id TEXT,
        micro_rush_id TEXT,
        session_id TEXT,
        model TEXT,
        status TEXT,
        started_at TEXT,
        finished_at TEXT,
        stop_reason TEXT,
        pull_request_url TEXT
    );
    """,
    """
    CREATE TABLE tool_calls (
        event_id TEXT PRIMARY KEY REFERENCES events(event_id),
        run_id TEXT NOT NULL,
        action TEXT NOT NULL,
        tool_name TEXT,
        tool_call_id TEXT,
        is_error INTEGER,
        payload_json TEXT NOT NULL
    );
    CREATE TABLE commands (
        event_id TEXT PRIMARY KEY REFERENCES events(event_id),
        run_id TEXT NOT NULL,
        action TEXT NOT NULL,
        payload_json TEXT NOT NULL
    );
    CREATE TABLE file_changes (
        event_id TEXT PRIMARY KEY REFERENCES events(event_id),
        run_id TEXT NOT NULL,
        action TEXT NOT NULL,
        payload_json TEXT NOT NULL
    );
    CREATE TABLE tests (
        event_id TEXT PRIMARY KEY REFERENCES events(event_id),
        run_id TEXT NOT NULL,
        action TEXT NOT NULL,
        payload_json TEXT NOT NULL
    );
    CREATE TABLE dependencies (
        event_id TEXT PRIMARY KEY REFERENCES events(event_id),
        run_id TEXT NOT NULL,
        action TEXT NOT NULL,
        payload_json TEXT NOT NULL
    );
    CREATE TABLE network_events (
        event_id TEXT PRIMARY KEY REFERENCES events(event_id),
        run_id TEXT NOT NULL,
        action TEXT NOT NULL,
        payload_json TEXT NOT NULL
    );
    CREATE TABLE harness_events (
        event_id TEXT PRIMARY KEY REFERENCES events(event_id),
        run_id TEXT NOT NULL,
        action TEXT NOT NULL,
        payload_json TEXT NOT NULL
    );
    CREATE TABLE git_events (
        event_id TEXT PRIMARY KEY REFERENCES events(event_id),
        run_id TEXT NOT NULL,
        action TEXT NOT NULL,
        payload_json TEXT NOT NULL
    );
    CREATE TABLE telegram_events (
        event_id TEXT PRIMARY KEY REFERENCES events(event_id),
        run_id TEXT NOT NULL,
        action TEXT NOT NULL,
        payload_json TEXT NOT NULL
    );
    CREATE TABLE model_messages (
        event_id TEXT PRIMARY KEY REFERENCES events(event_id),
        run_id TEXT NOT NULL,
        action TEXT NOT NULL,
        role TEXT,
        content TEXT,
        payload_json TEXT NOT NULL
    );
    """,
]


def migrate(connection) -> None:
    """Apply every missing migration transactionally."""

    connection.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    applied = {
        row[0]
        for row in connection.execute("SELECT version FROM schema_migrations ORDER BY version")
    }

    for version, migration in enumerate(MIGRATIONS, start=1):
        if version in applied:
            continue
        with connection:
            connection.executescript(migration)
            connection.execute(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (?, datetime('now'))",
                (version,),
            )

