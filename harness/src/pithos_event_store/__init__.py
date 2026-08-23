"""Ingest append-only Pithos event streams into reconstructible SQLite projections."""

from .store import EventStore, IngestionError

__all__ = ["EventStore", "IngestionError"]

