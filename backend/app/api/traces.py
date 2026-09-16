from fastapi import APIRouter, Depends, HTTPException, status

from app.models.schemas import TraceEventOut, TraceListOut, TraceOut
from app.trace.store import TraceStore

from .deps import get_trace_store

router = APIRouter(tags=["traces"])


@router.get("/trace/{conversation_id}", response_model=TraceListOut)
def get_traces(
    conversation_id: str,
    knowledge_base_id: str = "default",
    trace_store: TraceStore = Depends(get_trace_store),
) -> TraceListOut:
    traces = trace_store.get_traces(knowledge_base_id, conversation_id)
    if not traces:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Trace not found"
        )
    return TraceListOut(
        conversation_id=conversation_id,
        knowledge_base_id=knowledge_base_id,
        traces=[_to_trace(trace) for trace in traces],
    )


def _to_trace(trace: dict) -> TraceOut:
    return TraceOut(
        trace_id=trace["trace_id"],
        conversation_id=trace["conversation_id"],
        knowledge_base_id=trace["knowledge_base_id"],
        question=trace["question"],
        status=trace["status"],
        started_at=trace["started_at"],
        completed_at=trace["completed_at"],
        latency_ms=trace["latency_ms"],
        events=[TraceEventOut(**event) for event in trace["events"]],
    )