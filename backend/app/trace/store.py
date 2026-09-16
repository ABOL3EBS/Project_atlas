"""SQLite persistence for execution traces.

Mirrors the existing `ConversationStore`/`DocumentStore` pattern (stdlib sqlite3,
one store per DB file, `knowledge_base_id` scoping on every query). Trace data is
deliberately separate from conversation-memory data: they serve different
purposes.
"""

from __future__ import annotations

import json
from pathlib import Path
from sqlite3 import connect

from .events import TraceEvent
from .recorder import TraceRecorder


class TraceStore:
    def __init__(self, db_path: str):
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with connect(self._path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS traces (
                    trace_id TEXT PRIMARY KEY,
                    conversation_id TEXT,
                    knowledge_base_id TEXT NOT NULL,
                    question TEXT,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    latency_ms REAL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS trace_events (
                    id TEXT PRIMARY KEY,
                    trace_id TEXT NOT NULL,
                    conversation_id TEXT,
                    knowledge_base_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    latency_ms REAL,
                    metadata TEXT,
                    error TEXT
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_traces_conversation "
                "ON traces(knowledge_base_id, conversation_id)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_trace_events_trace "
                "ON trace_events(trace_id)"
            )

    def save_trace(self, trace: TraceRecorder) -> None:
        events = trace.event_records()
        with connect(self._path) as connection:
            connection.execute(
                "INSERT INTO traces "
                "(trace_id, conversation_id, knowledge_base_id, question, status, "
                "started_at, completed_at, latency_ms) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    trace.trace_id,
                    trace.conversation_id,
                    trace.knowledge_base_id,
                    trace.question,
                    trace.status or "unknown",
                    trace.started_at,
                    trace.completed_at,
                    trace.total_latency_ms,
                ),
            )
            connection.executemany(
                "INSERT INTO trace_events "
                "(id, trace_id, conversation_id, knowledge_base_id, event_type, "
                "status, timestamp, latency_ms, metadata, error) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [_event_row(event) for event in events],
            )

    def get_traces(self, knowledge_base_id: str, conversation_id: str) -> list[dict]:
        with connect(self._path) as connection:
            rows = connection.execute(
                "SELECT trace_id, conversation_id, knowledge_base_id, question, status, "
                "started_at, completed_at, latency_ms FROM traces "
                "WHERE knowledge_base_id = ? AND conversation_id = ? "
                "ORDER BY started_at, rowid",
                (knowledge_base_id, conversation_id),
            ).fetchall()
        return [self._trace_to_dict(connection, row) for row in rows]

    def get_trace(self, knowledge_base_id: str, trace_id: str) -> dict | None:
        with connect(self._path) as connection:
            row = connection.execute(
                "SELECT trace_id, conversation_id, knowledge_base_id, question, status, "
                "started_at, completed_at, latency_ms FROM traces "
                "WHERE knowledge_base_id = ? AND trace_id = ?",
                (knowledge_base_id, trace_id),
            ).fetchone()
        if not row:
            return None
        return self._trace_to_dict(connection, row)

    def _trace_to_dict(self, connection, row: tuple) -> dict:
        trace_id = row[0]
        with connection:
            event_rows = connection.execute(
                "SELECT id, trace_id, conversation_id, knowledge_base_id, event_type, "
                "status, timestamp, latency_ms, metadata, error FROM trace_events "
                "WHERE trace_id = ? ORDER BY timestamp, rowid",
                (trace_id,),
            ).fetchall()
        return {
            "trace_id": row[0],
            "conversation_id": row[1],
            "knowledge_base_id": row[2],
            "question": row[3],
            "status": row[4],
            "started_at": row[5],
            "completed_at": row[6],
            "latency_ms": row[7],
            "events": [_event_to_dict(event_row) for event_row in event_rows],
        }


def _event_row(event: TraceEvent) -> tuple:
    return (
        event.event_id,
        event.trace_id,
        event.conversation_id,
        event.knowledge_base_id,
        event.event_type,
        event.status,
        event.timestamp,
        event.latency_ms,
        json.dumps(event.metadata),
        json.dumps(event.error) if event.error is not None else None,
    )


def _event_to_dict(row: tuple) -> dict:
    metadata = json.loads(row[8]) if row[8] else {}
    error = json.loads(row[9]) if row[9] else None
    event = {
        "event_id": row[0],
        "trace_id": row[1],
        "event_type": row[4],
        "status": row[5],
        "timestamp": row[6],
        "knowledge_base_id": row[3],
        "metadata": metadata,
    }
    if row[2] is not None:
        event["conversation_id"] = row[2]
    if row[7] is not None:
        event["latency_ms"] = round(row[7], 3)
    if error:
        event["error"] = error
    return event