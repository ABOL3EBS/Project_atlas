"""In-memory trace recorder.

The recorder is what the agent talks to: it turns execution events into a
chronologically ordered list of :class:`TraceEvent` objects. Persistence lives
behind :class:`TraceStore`, so the agent never touches SQLite directly.
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager

from app.services.document_store import utc_now

from .events import TraceEvent, TraceEventType

logger = logging.getLogger("atlas.trace")

_MAX_ERROR_MESSAGE = 500


def now_ms() -> float:
    return time.perf_counter() * 1000.0


def safe_error_message(message: str) -> str:
    return message[: _MAX_ERROR_MESSAGE]


class TraceRecorder:
    def __init__(
        self,
        *,
        knowledge_base_id: str,
        conversation_id: str | None = None,
        question: str | None = None,
    ):
        from uuid import uuid4

        self.trace_id = str(uuid4())
        self.knowledge_base_id = knowledge_base_id
        self.conversation_id = conversation_id
        self.question = question
        self.started_at = utc_now()
        self.completed_at: str | None = None
        self.status: str | None = None
        self.total_latency_ms: float | None = None
        self._events: list[TraceEvent] = []
        self._started = now_ms()

    def record(
        self,
        event_type: TraceEventType | str,
        *,
        status: str = "completed",
        latency_ms: float | None = None,
        metadata: dict | None = None,
        error: dict | None = None,
    ) -> TraceEvent:
        event = TraceEvent(
            trace_id=self.trace_id,
            knowledge_base_id=self.knowledge_base_id,
            conversation_id=self.conversation_id,
            event_type=str(event_type),
            status=status,
            timestamp=utc_now(),
            latency_ms=latency_ms,
            metadata=dict(metadata or {}),
            error=error,
        )
        self._events.append(event)
        return event

    @contextmanager
    def span(self, event_type: TraceEventType, *, metadata: dict | None = None):
        """Record a single completed/failed event covering a block's wall time."""
        start = now_ms()
        try:
            yield
        except Exception as error:
            self.record(
                event_type,
                status="failed",
                latency_ms=now_ms() - start,
                metadata=metadata,
                error=_make_error("block", error),
            )
            raise
        else:
            self.record(
                event_type,
                status="completed",
                latency_ms=now_ms() - start,
                metadata=metadata,
            )

    def error(self, *, component: str, code: str, message: str) -> None:
        self.record(
            TraceEventType.ERROR,
            status="failed",
            error=_make_error(component, message, code),
        )

    def complete(self, *, status: str = "completed") -> None:
        self.status = status
        self.completed_at = utc_now()
        self.total_latency_ms = now_ms() - self._started

    def events(self) -> list[dict]:
        return [event.to_dict() for event in self._events]

    def event_records(self) -> list[TraceEvent]:
        return list(self._events)

    def to_trace_dict(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "conversation_id": self.conversation_id,
            "knowledge_base_id": self.knowledge_base_id,
            "question": self.question,
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "latency_ms": self.total_latency_ms,
        }


def _make_error(component: str, message_or_error: Exception | str, code: str | None = None):
    if isinstance(message_or_error, Exception):
        code = code or type(message_or_error).__name__.upper()
        message = safe_error_message(str(message_or_error))
    else:
        message = safe_error_message(message_or_error)
    return {"component": component, "code": code, "message": message}