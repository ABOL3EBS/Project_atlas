"""Strongly typed execution-trace event model.

The trace records *observable execution metadata* — which tool ran, how many
chunks were retrieved, whether grounding passed, which citations were verified,
and how long each stage took. It intentionally never stores model reasoning,
system prompts, or retrieved document text.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from uuid import uuid4


class TraceEventType(StrEnum):
    TRACE_STARTED = "trace_started"
    AGENT_STARTED = "agent_started"
    DECISION = "decision"
    TOOL_CALL = "tool_call"
    RETRIEVAL = "retrieval"
    RERANKING = "reranking"
    GROUNDING = "grounding"
    CITATION = "citation"
    GENERATION_STARTED = "generation_started"
    GENERATION_COMPLETED = "generation_completed"
    ERROR = "error"
    TRACE_COMPLETED = "trace_completed"


@dataclass
class TraceEvent:
    trace_id: str
    knowledge_base_id: str
    event_type: str
    status: str
    timestamp: str
    event_id: str | None = None
    conversation_id: str | None = None
    latency_ms: float | None = None
    metadata: dict = field(default_factory=dict)
    error: dict | None = None

    def __post_init__(self) -> None:
        self.event_id = self.event_id or str(uuid4())

    def to_dict(self) -> dict:
        event: dict = {
            "event_id": self.event_id,
            "trace_id": self.trace_id,
            "event_type": self.event_type,
            "status": self.status,
            "timestamp": self.timestamp,
            "knowledge_base_id": self.knowledge_base_id,
        }
        if self.conversation_id is not None:
            event["conversation_id"] = self.conversation_id
        if self.latency_ms is not None:
            event["latency_ms"] = round(self.latency_ms, 3)
        if self.metadata:
            event["metadata"] = self.metadata
        if self.error:
            event["error"] = self.error
        return event