import pytest

from app.agent.agent import AtlasAgent
from app.memory.conversation_store import ConversationStore
from app.memory.selector import MemorySelector
from app.retrieval.retriever import RetrievedChunk
from app.trace import TraceEventType, TraceRecorder, TraceStore
from tests.conftest import FakeEmbeddingProvider, FakeLLMProvider, FakeVectorStore


class StubRetriever:
    def __init__(self, chunks=None):
        self._chunks = chunks or []

    def search(self, knowledge_base_id, query, top_k=None):
        return self._chunks

    def search_in_document(self, knowledge_base_id, query, document_id, top_k=None):
        return self._chunks


class _FakeDocumentStore:
    def __init__(self, documents=None):
        self._documents = documents or [
            {"id": "d-1", "name": "budget.pdf", "status": "indexed"}
        ]

    def list(self, knowledge_base_id):
        return self._documents


def _chunk(score=0.9):
    return RetrievedChunk(
        text="The quarterly budget is 40k.",
        chunk_id="c-1",
        document_id="d-1",
        document_name="budget.pdf",
        page=3,
        section="Q3",
        score=score,
    )


SEARCH_PLAN = '{"tool": "search_knowledge_base", "arguments": {"query": "budget", "top_k": 4}}'


def _agent(chunks=None, plan=None, *, trace_db=None, conversation_db=None):
    return AtlasAgent(
        retriever=StubRetriever(chunks),
        llm_provider=FakeLLMProvider(tokens=["A", "nswer"], plan_response=plan),
        vector_store=FakeVectorStore(),
        conversation_store=(
            ConversationStore(conversation_db) if conversation_db else None
        ),
        memory_selector=MemorySelector(FakeEmbeddingProvider()),
        trace_store=TraceStore(trace_db) if trace_db else None,
    )


async def _events(agent, question="budget?", conversation_id=None):
    return [event async for event in agent.run("kb-a", question, conversation_id)]


async def _run_persisted(agent, trace_db, *, question="budget?"):
    """Run an agent with conversation_db + trace_db; return (conversation_id, trace)."""
    conversation_id = None
    async for event in agent.run("kb-a", question):
        if event["type"] == "conversation":
            conversation_id = event["conversation_id"]
    store = TraceStore(trace_db)
    trace = store.get_traces("kb-a", conversation_id)
    assert trace, "trace was not persisted"
    return conversation_id, trace[0]


def _event_types(trace: dict) -> list[str]:
    return [event["event_type"] for event in trace["events"]]


# ── TraceRecorder ──────────────────────────────────────────────────────


def test_recorder_returns_ordered_unique_events():
    trace = TraceRecorder(knowledge_base_id="kb-a")
    trace.record(TraceEventType.TRACE_STARTED, status="started")
    trace.record(TraceEventType.DECISION)
    trace.complete(status="completed")

    events = trace.events()
    assert len(events) == 2
    assert [event["event_type"] for event in events] == [
        "trace_started",
        "decision",
    ]
    assert events[0]["event_id"] != events[1]["event_id"]
    assert events[0]["knowledge_base_id"] == "kb-a"


def test_recorder_span_records_latency_and_reraises():
    trace = TraceRecorder(knowledge_base_id="kb-a")

    with pytest.raises(RuntimeError):
        with trace.span(TraceEventType.TOOL_CALL):
            raise RuntimeError("boom")

    events = trace.events()
    assert events[0]["event_type"] == "tool_call"
    assert events[0]["status"] == "failed"
    assert events[0]["latency_ms"] >= 0
    assert events[0]["error"]["code"] == "RUNTIMEERROR"
    assert events[0]["error"]["message"] == "boom"


def test_recorder_complete_sets_trace_wide_fields():
    trace = TraceRecorder(knowledge_base_id="kb-a")
    assert trace.status is None
    trace.complete(status="failed")
    assert trace.status == "failed"
    assert trace.completed_at
    assert trace.total_latency_ms >= 0


def test_trace_store_roundtrips_trace_with_ordered_events(tmp_path):
    store = TraceStore(str(tmp_path / "traces.db"))
    trace = TraceRecorder(knowledge_base_id="kb-a", conversation_id="conv-1")
    trace.record(TraceEventType.TRACE_STARTED, status="started")
    trace.record(TraceEventType.RETRIEVAL, metadata={"candidates": 4, "returned": 4})
    trace.complete(status="completed")
    store.save_trace(trace)

    saved = store.get_traces("kb-a", "conv-1")
    assert len(saved) == 1
    assert saved[0]["status"] == "completed"
    assert [event["event_type"] for event in saved[0]["events"]] == [
        "trace_started",
        "retrieval",
    ]
    assert saved[0]["events"][-1]["metadata"]["candidates"] == 4


def test_trace_store_isolated_by_knowledge_base(tmp_path):
    store = TraceStore(str(tmp_path / "traces.db"))
    trace = TraceRecorder(knowledge_base_id="kb-a", conversation_id="conv-1")
    trace.complete()
    store.save_trace(trace)
    assert store.get_traces("kb-b", "conv-1") == []
    assert store.get_trace("kb-b", trace.trace_id) is None
    assert store.get_trace("kb-a", trace.trace_id) is not None


# ── Agent trace recording ──────────────────────────────────────────────


async def test_direct_answer_trace_records_no_retrieval(tmp_path):
    trace_db = str(tmp_path / "traces.db")
    agent = _agent(
        plan='{"tool": "none", "arguments": {}}',
        trace_db=trace_db,
        conversation_db=str(tmp_path / "conversations.db"),
    )
    _, trace = await _run_persisted(agent, trace_db)
    types = _event_types(trace)
    assert "trace_started" in types
    assert "agent_started" in types
    assert "decision" in types
    assert "generation_started" in types
    assert "generation_completed" in types
    assert "retrieval" not in types
    assert "reranking" not in types
    assert "grounding" not in types
    assert "citation" not in types


async def test_search_flow_records_retrieval_and_reranking(tmp_path):
    trace_db = str(tmp_path / "traces.db")
    agent = _agent(
        [_chunk()],
        plan=SEARCH_PLAN,
        trace_db=trace_db,
        conversation_db=str(tmp_path / "conversations.db"),
    )
    _, trace = await _run_persisted(agent, trace_db)
    events = trace["events"]
    types = _event_types(trace)

    retrieval = next(e for e in events if e["event_type"] == "retrieval")
    assert retrieval["metadata"]["candidates"] == 1
    assert retrieval["metadata"]["returned"] == 1
    assert "reranking" in types
    assert "grounding" in types
    assert "citation" in types
    reranking = next(e for e in events if e["event_type"] == "reranking")
    assert reranking["metadata"]["method"] == "bm25"
    assert reranking["metadata"]["input_count"] == 1


async def test_grounding_rejected_when_no_evidence(tmp_path):
    trace_db = str(tmp_path / "traces.db")
    agent = _agent(
        [],
        plan=SEARCH_PLAN,
        trace_db=trace_db,
        conversation_db=str(tmp_path / "conversations.db"),
    )
    _, trace = await _run_persisted(agent, trace_db)

    grounding = next(
        e for e in trace["events"] if e["event_type"] == "grounding"
    )
    assert grounding["status"] == "rejected"
    assert grounding["metadata"]["rule"] == "threshold"
    assert grounding["metadata"]["score"] is None
    assert "citation" not in _event_types(trace)


async def test_retrieve_document_trace_has_no_reranking(tmp_path):
    trace_db = str(tmp_path / "traces.db")
    vector_store = FakeVectorStore()
    vector_store.chunked = [
        {
            "chunk_id": "d-1-0",
            "text": "The quarterly budget is 40k.",
            "document_id": "d-1",
            "document_name": "budget.pdf",
            "page": 3,
            "section": "Q3",
        }
    ]
    agent = AtlasAgent(
        retriever=StubRetriever(),
        llm_provider=FakeLLMProvider(
            tokens=["A", "nswer"],
            plan_response=(
                '{"tool": "retrieve_document", '
                '"arguments": {"document": "budget.pdf"}}'
            ),
        ),
        vector_store=vector_store,
        document_store=_FakeDocumentStore(),
        conversation_store=ConversationStore(str(tmp_path / "conversations.db")),
        trace_store=TraceStore(trace_db),
    )
    _, trace = await _run_persisted(agent, trace_db)
    types = _event_types(trace)

    assert "retrieval" in types
    assert "reranking" not in types
    grounding = next(e for e in trace["events"] if e["event_type"] == "grounding")
    assert grounding["metadata"]["rule"] == "any_evidence"
    assert grounding["status"] == "passed"


async def test_tool_failure_records_failed_trace(tmp_path):
    class ExplodingRetriever:
        def search(self, knowledge_base_id, query, top_k=None):
            raise RuntimeError("vector store unavailable")

    trace_db = str(tmp_path / "traces.db")
    agent = AtlasAgent(
        retriever=ExplodingRetriever(),
        llm_provider=FakeLLMProvider(plan_response=SEARCH_PLAN),
        vector_store=FakeVectorStore(),
        conversation_store=ConversationStore(str(tmp_path / "conversations.db")),
        trace_store=TraceStore(trace_db),
    )
    statuses = []
    conversation_id = None
    async for event in agent.run("kb-a", "budget?"):
        if event["type"] == "conversation":
            conversation_id = event["conversation_id"]
        if event["type"] == "trace_completed":
            statuses.append(event["status"])
        if event["type"] == "error":
            assert "vector store unavailable" in event["message"]
    assert statuses and statuses[0] == "failed"

    store = TraceStore(trace_db)
    trace = store.get_traces("kb-a", conversation_id)
    assert trace, "failed trace was not persisted"
    trace = trace[0]
    assert trace["status"] == "failed"
    assert "error" in _event_types(trace)
    error = next(e for e in trace["events"] if e["event_type"] == "error")
    assert error["error"]["code"] == "AGENT_FAILED"
    assert "vector store unavailable" in error["error"]["message"]


async def test_llm_stream_failure_records_failed_trace(tmp_path):
    class RaisingLLM:
        async def generate(
            self, prompt, *, system=None, json_mode=False
        ) -> str:
            return "not a decision"

        async def stream(self, prompt, *, system=None):
            raise RuntimeError("llm generation failed")
            yield  # pragma: no cover

    trace_db = str(tmp_path / "traces.db")
    agent = AtlasAgent(
        retriever=StubRetriever([_chunk()]),
        llm_provider=RaisingLLM(),
        vector_store=FakeVectorStore(),
        trace_store=TraceStore(trace_db),
    )
    final_events = [
        event
        async for event in agent.run("kb-a", "budget?")
        if event["type"] in {"error", "trace_completed"}
    ]
    assert any(event["type"] == "error" for event in final_events)
    completed = [e for e in final_events if e["type"] == "trace_completed"]
    assert completed and completed[0]["status"] == "failed"


async def test_trace_never_exposes_reasoning_or_prompts(tmp_path):
    trace_db = str(tmp_path / "traces.db")
    agent = _agent(
        [_chunk()],
        plan=SEARCH_PLAN,
        trace_db=trace_db,
        conversation_db=str(tmp_path / "conversations.db"),
    )
    conversation_id, trace = await _run_persisted(agent, trace_db)
    assert conversation_id

    forbidden = {
        "reasoning", "chain_of_thought", "system_prompt", "prompt",
        "arguments", "query", "secret", "api_key", "text",
    }
    serialized = f"{trace}"
    for event in trace["events"]:
        for key in event["metadata"]:
            assert not any(word in str(key).lower() for word in forbidden)
    assert "The quarterly budget is 40k." not in serialized


async def test_multiple_traces_persist_in_order(tmp_path):
    trace_db = str(tmp_path / "traces.db")
    agent = _agent(
        plan='{"tool": "none", "arguments": {}}',
        trace_db=trace_db,
        conversation_db=str(tmp_path / "conversations.db"),
    )
    conversation_id = None
    for _ in range(2):
        async for event in agent.run("kb-a", "budget?", conversation_id):
            if event["type"] == "conversation":
                conversation_id = event["conversation_id"]

    store = TraceStore(trace_db)
    traces = store.get_traces("kb-a", conversation_id)
    assert len(traces) == 2
    assert traces[0]["trace_id"] != traces[1]["trace_id"]


async def test_trace_events_carry_conversation_id_when_auto_created(tmp_path):
    trace_db = str(tmp_path / "traces.db")
    agent = _agent(
        [_chunk()],
        plan=SEARCH_PLAN,
        trace_db=trace_db,
        conversation_db=str(tmp_path / "conversations.db"),
    )
    _, trace = await _run_persisted(agent, trace_db)
    assert all(e["conversation_id"] for e in trace["events"])


# ── SSE events ─────────────────────────────────────────────────────────


async def test_search_flow_emits_new_sse_event_types():
    agent = _agent([_chunk()], plan=SEARCH_PLAN)
    events = await _events(agent)
    types = {event["type"] for event in events}
    assert {"trace", "reranking", "grounding", "citation", "trace_completed"} <= types
    assert events[0]["type"] == "conversation"
    trace_event = next(e for e in events if e["type"] == "trace")
    assert trace_event["trace_id"]