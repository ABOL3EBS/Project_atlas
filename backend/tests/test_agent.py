from app.agent.agent import AtlasAgent
from app.agent.decision import TOOL_RETRIEVE, TOOL_SEARCH
from app.agent.grounding import NOT_FOUND_MESSAGE, SYSTEM_PROMPT
from app.memory.conversation_store import ConversationStore
from app.memory.selector import MemorySelector
from app.retrieval.retriever import RetrievedChunk
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


def _agent(chunks=None, plan=None, *, conversation_db=None, with_memory=False):
    return AtlasAgent(
        retriever=StubRetriever(chunks),
        llm_provider=FakeLLMProvider(tokens=["A", "nswer"], plan_response=plan),
        vector_store=FakeVectorStore(),
        conversation_store=(
            ConversationStore(conversation_db) if conversation_db else None
        ),
        memory_selector=MemorySelector(FakeEmbeddingProvider()) if with_memory else None,
    )


async def _events(agent, question="budget?", conversation_id=None):
    return [event async for event in agent.run("kb-a", question, conversation_id)]


async def test_direct_answer_skips_retrieval():
    events = await _events(_agent(plan='{"tool": "none", "arguments": {}}'))
    assert not any(event["type"] == "retrieval" for event in events)
    token_text = "".join(e["text"] for e in events if e["type"] == "token")
    assert token_text == "Answer"
    done = [e for e in events if e["type"] == "done"]
    assert done and done[0]["citations"] == []
    decision = [e for e in events if e["type"] == "decision"][0]
    assert decision["source"] == "direct"
    assert decision["tool"] is None


async def test_search_flow_emits_cited_answer():
    plan = '{"tool": "search_knowledge_base", "arguments": {"query": "budget", "top_k": 4}}'
    events = await _events(_agent([_chunk()], plan=plan))
    assert any(e["type"] == "tool_call" and e["tool"] == TOOL_SEARCH for e in events)
    retrieval = [e for e in events if e["type"] == "retrieval"]
    assert retrieval and retrieval[0]["count"] == 1
    token_text = "".join(e["text"] for e in events if e["type"] == "token")
    assert token_text == "Answer"
    done = [e for e in events if e["type"] == "done"][0]
    assert done["citations"] and done["citations"][0]["document_name"] == "budget.pdf"


async def test_unmatched_question_reports_not_found():
    plan = '{"tool": "search_knowledge_base", "arguments": {"query": "x", "top_k": 4}}'
    events = await _events(_agent([], plan=plan))
    assert any(
        e["type"] == "answer" and e["text"] == NOT_FOUND_MESSAGE for e in events
    )
    assert not any(e["type"] == "token" for e in events)


async def test_retrieve_document_is_intent_gated_not_score_gated():
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
            plan_response='{"tool": "retrieve_document", "arguments": {"document": "budget.pdf"}}',
        ),
        vector_store=vector_store,
        document_store=_FakeDocumentStore(),
    )
    events = await _events(agent)
    assert any(e["type"] == "tool_call" and e["tool"] == TOOL_RETRIEVE for e in events)
    assert any(e["type"] == "done" for e in events)
    assert not any(e["type"] == "answer" for e in events)


async def test_malformed_decision_falls_back_to_search():
    llm = FakeLLMProvider(tokens=["ans"], plan_response="totally broken response")
    agent = AtlasAgent(
        retriever=StubRetriever([_chunk()]),
        llm_provider=llm,
        vector_store=FakeVectorStore(),
    )
    events = await _events(agent)
    tool_calls = [e for e in events if e["type"] == "tool_call"]
    assert tool_calls and tool_calls[0]["tool"] == TOOL_SEARCH
    assert any(e["type"] == "retrieval" for e in events)


async def test_memory_flow_answers_from_conversation_when_kb_empty(tmp_path):
    conversation_db = str(tmp_path / "conversations.db")
    agent = _agent(
        [],
        plan='{"tool": "get_conversation_context", "arguments": {"question": "budget"}}',
        conversation_db=conversation_db,
        with_memory=True,
    )
    conversation_id = agent._conversation_store.ensure_conversation("kb-a")
    agent._conversation_store.append_message(conversation_id, "user", "what is the budget?")
    agent._conversation_store.append_message(
        conversation_id, "assistant", "the quarterly budget is 40k"
    )

    events = await _events(agent, conversation_id=conversation_id)
    memory = [e for e in events if e["type"] == "memory"]
    assert memory and memory[0]["count"] >= 1
    assert any(e["type"] == "done" for e in events)
    assert not any(e["type"] == "answer" for e in events)


async def test_memory_flow_falls_back_to_not_found_without_recall(tmp_path):
    conversation_db = str(tmp_path / "conversations.db")
    agent = _agent(
        [],
        plan='{"tool": "get_conversation_context", "arguments": {"question": "budget"}}',
        conversation_db=conversation_db,
        with_memory=True,
    )
    conversation_id = agent._conversation_store.ensure_conversation("kb-a")
    events = await _events(agent, conversation_id=conversation_id)
    assert any(
        e["type"] == "answer" and e["text"] == NOT_FOUND_MESSAGE for e in events
    )


async def test_conversation_persists_user_and_assistant_messages(tmp_path):
    conversation_db = str(tmp_path / "conversations.db")
    agent = _agent(
        [_chunk()],
        plan='{"tool": "search_knowledge_base", "arguments": {"query": "budget", "top_k": 4}}',
        conversation_db=conversation_db,
    )
    conversation_id = agent._conversation_store.ensure_conversation("kb-a")
    await _events(agent, conversation_id=conversation_id)

    messages = agent._conversation_store.list_messages(conversation_id)
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[0]["content"] == "budget?"
    assert messages[1]["content"] == "Answer"


async def test_agent_uses_grounded_system_prompt_for_generated_answers():
    captured = {}

    class CaptureLLM(FakeLLMProvider):
        async def stream(self, prompt, *, system=None):
            captured["system"] = system
            yield "ok"

    agent = AtlasAgent(
        retriever=StubRetriever([_chunk()]),
        llm_provider=CaptureLLM(
            plan_response=(
                '{"tool": "search_knowledge_base", '
                '"arguments": {"query": "budget", "top_k": 4}}'
            )
        ),
        vector_store=FakeVectorStore(),
    )
    await _events(agent)
    assert captured["system"] == SYSTEM_PROMPT