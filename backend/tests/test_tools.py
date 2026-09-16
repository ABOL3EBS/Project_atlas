from app.agent.base import ToolContext
from app.agent.tools import (
    CompareDocumentsTool,
    GetConversationContextTool,
    RetrieveDocumentTool,
    SearchKnowledgeBaseTool,
)
from app.memory.conversation_store import ConversationStore
from app.memory.selector import MemorySelector
from app.retrieval.retriever import RetrievedChunk
from tests.conftest import FakeEmbeddingProvider, FakeVectorStore


class StubRetriever:
    def __init__(self):
        self.queries = []

    def search(self, knowledge_base_id, query, top_k=None):
        self.queries.append(("search", knowledge_base_id, query, top_k))
        return [
            RetrievedChunk(
                text=query,
                chunk_id="c-1",
                document_id="d-1",
                document_name="install.pdf",
                page=18,
                section=None,
                score=0.9,
            )
        ]

    def search_in_document(self, knowledge_base_id, query, document_id, top_k=None):
        self.queries.append(("in-doc", knowledge_base_id, query, document_id, top_k))
        return [
            RetrievedChunk(
                text=query,
                chunk_id=f"{document_id}-0",
                document_id=document_id,
                document_name="install.pdf",
                page=1,
                section=None,
                score=0.8,
            )
        ]


def _context(documents=None):
    return ToolContext(
        knowledge_base_id="kb-a",
        retriever=StubRetriever(),
        vector_store=FakeVectorStore(),
        documents=documents
        or [
            {"id": "doc-1", "name": "install.pdf", "status": "indexed"},
            {"id": "doc-2", "name": "SECURITY.md", "status": "indexed"},
        ],
    )


async def test_search_tool_returns_evidence_and_passes_top_k():
    retriever = StubRetriever()
    tool = SearchKnowledgeBaseTool(retriever)
    result = await tool.execute(
        _context(), {"query": "requirements", "top_k": 2}
    )
    assert result.evidence
    assert result.evidence[0].chunk_id == "c-1"
    assert retriever.queries[-1] == ("search", "kb-a", "requirements", 2)


async def test_search_tool_clamps_top_k():
    retriever = StubRetriever()
    tool = SearchKnowledgeBaseTool(retriever)
    await tool.execute(_context(), {"query": "q", "top_k": 999})
    assert retriever.queries[-1][3] <= 8


class EmptyRetriever(StubRetriever):
    def search(self, knowledge_base_id, query, top_k=None):
        return []


async def test_search_tool_reports_empty_summary():
    result = await SearchKnowledgeBaseTool(EmptyRetriever()).execute(
        _context(), {"query": "q"}
    )
    assert not result.evidence
    assert "No passages" in (result.summary or "")


async def test_retrieve_document_resolves_and_returns_chunks():
    vector_store = FakeVectorStore()
    vector_store.chunked = [
        {
            "chunk_id": "doc-1-0",
            "text": "first chunk",
            "document_id": "doc-1",
            "document_name": "install.pdf",
            "page": 1,
            "section": None,
        },
        {
            "chunk_id": "doc-1-1",
            "text": "second chunk",
            "document_id": "doc-1",
            "document_name": "install.pdf",
            "page": 2,
            "section": None,
        },
    ]
    tool = RetrieveDocumentTool(StubRetriever(), vector_store)
    result = await tool.execute(_context(), {"document": "install.pdf"})
    assert [chunk.chunk_id for chunk in result.evidence] == ["doc-1-0", "doc-1-1"]
    assert all(chunk.score == 0.0 for chunk in result.evidence)


async def test_retrieve_document_matches_case_insensitively():
    vector_store = FakeVectorStore()
    vector_store.chunked = [
        {
            "chunk_id": "doc-2-0",
            "text": "content",
            "document_id": "doc-2",
            "document_name": "SECURITY.md",
            "page": None,
            "section": "Overview",
        }
    ]
    tool = RetrieveDocumentTool(StubRetriever(), vector_store)
    result = await tool.execute(_context(), {"document": "security.md"})
    assert len(result.evidence) == 1


async def test_retrieve_document_unknown_name_returns_summary():
    tool = RetrieveDocumentTool(StubRetriever(), FakeVectorStore())
    result = await tool.execute(_context(), {"document": "missing.pdf"})
    assert not result.evidence
    assert "No document named 'missing.pdf'" in (result.summary or "")


async def test_compare_document_queries_each_resolved_document():
    retriever = StubRetriever()
    tool = CompareDocumentsTool(retriever)
    result = await tool.execute(
        _context(), {"documents": ["install.pdf", "SECURITY.md"], "question": "compare"}
    )
    assert len(result.evidence) == 2
    assert retriever.queries[0][2] == "compare"


async def test_compare_document_unknown_names_reported_in_summary():
    retriever = StubRetriever()
    tool = CompareDocumentsTool(retriever)
    result = await tool.execute(
        _context(), {"documents": ["install.pdf", "nope.txt"], "question": "compare"}
    )
    assert result.evidence
    assert "nope.txt" in (result.summary or "")


async def test_memory_tool_without_store_returns_summary():
    tool = GetConversationContextTool()
    context = ToolContext(
        knowledge_base_id="kb-a",
        retriever=StubRetriever(),
        vector_store=FakeVectorStore(),
        conversation_id=None,
    )
    result = await tool.execute(context, {"question": "what did we say?"})
    assert not result.evidence
    assert "No prior conversation" in (result.summary or "")


async def test_memory_tool_selects_previous_messages(tmp_path):
    store = ConversationStore(str(tmp_path / "conversations.db"))
    conversation_id = store.ensure_conversation("kb-a")
    store.append_message(conversation_id, "user", "budget for the quarter?")
    store.append_message(conversation_id, "assistant", "the quarterly budget is 40k")

    vectors = {
        "budget": [1.0, 0.0, 0.0],
        "budget for the quarter?": [1.0, 0.0, 0.0],
        "the quarterly budget is 40k": [1.0, 0.0, 0.0],
    }
    selector = MemorySelector(
        _DeterministicEmbedding(vectors),
    )
    tool = GetConversationContextTool()
    context = ToolContext(
        knowledge_base_id="kb-a",
        retriever=StubRetriever(),
        vector_store=FakeVectorStore(),
        conversation_id=conversation_id,
        memory_store=store,
        memory_selector=selector,
    )
    result = await tool.execute(context, {"question": "budget"})
    assert "the quarterly budget is 40k" in (result.summary or "")


class _DeterministicEmbedding(FakeEmbeddingProvider):
    def __init__(self, vectors: dict[str, list[float]]):
        self._vectors = vectors
        self._default = [0.0, 0.0, 0.0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vectors.get(text, self._default) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vectors.get(text, self._default)