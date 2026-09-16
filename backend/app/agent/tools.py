from app.retrieval.retriever import RetrievedChunk

from .base import Tool, ToolContext, ToolResult

RETRIEVE_DOCUMENT_LIMIT = 12
TOOL_SEARCH_TOP_K = 4


def _clamp_top_k(top_k: object, default: int) -> int:
    if not isinstance(top_k, int) or isinstance(top_k, bool):
        return default
    return max(1, min(top_k, 8))


def _now_ms() -> float:
    import time

    return time.perf_counter() * 1000.0


def _bm25_rerank(query: str, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    """Re-order the retrieved pool by BM25 lexical relevance.

    M4 measured BM25 reranking as the only adopted retrieval improvement; this
    wires it into the production search path (which M4 docs already claimed) so
    it exercises the same `BM25Reranker` the experiments used. The pool is the
    embedding top-k results, so the rerank reorders within that set; a larger
    cross-corpus candidate pool is a retrieval experiment, out of scope for M5.
    """
    from app.retrieval.pipelines import BM25Reranker

    reranker = BM25Reranker([chunk.text for chunk in chunks])
    return reranker.rerank(query, chunks, None)


def _resolve_document(documents: list[dict], name: str) -> dict | None:
    lowered = name.strip().lower()
    for document in documents:
        if document["name"] == name:
            return document
    for document in documents:
        if document["name"].lower() == lowered:
            return document
    return None


class SearchKnowledgeBaseTool(Tool):
    name = "search_knowledge_base"
    description = (
        "Search the uploaded knowledge base and return the most relevant passages. "
        "Use for factual questions about the uploaded documents."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "top_k": {"type": "integer"},
        },
        "required": ["query"],
    }

    def __init__(self, retriever):
        self._retriever = retriever

    async def execute(self, context: ToolContext, arguments: dict) -> ToolResult:
        query = arguments["query"]
        top_k = _clamp_top_k(arguments.get("top_k"), TOOL_SEARCH_TOP_K)
        start = _now_ms()
        chunks = self._retriever.search(
            context.knowledge_base_id, query, top_k=top_k
        )
        search_ms = _now_ms() - start
        if not chunks:
            return ToolResult(
                summary="No passages in the knowledge base matched the query.",
                candidates=0,
                timings={"search": search_ms},
            )
        start = _now_ms()
        reranked = _bm25_rerank(query, chunks)
        rerank_ms = _now_ms() - start
        return ToolResult(
            evidence=reranked,
            candidates=len(chunks),
            timings={"search": search_ms, "rerank": rerank_ms},
        )


class RetrieveDocumentTool(Tool):
    name = "retrieve_document"
    description = (
        "Retrieve the full text chunks of one specific document for broader context. "
        "Use when the user asks about an entire document."
    )
    input_schema = {
        "type": "object",
        "properties": {"document": {"type": "string"}},
        "required": ["document"],
    }

    def __init__(self, retriever, vector_store):
        self._retriever = retriever
        self._vector_store = vector_store

    async def execute(self, context: ToolContext, arguments: dict) -> ToolResult:
        document = _resolve_document(context.documents, arguments["document"])
        if document is None:
            return ToolResult(
                summary=(
                    f"No document named '{arguments['document']}' exists in this "
                    "knowledge base."
                )
            )
        items = self._vector_store.get_document_chunks(
            context.knowledge_base_id, document["id"], limit=RETRIEVE_DOCUMENT_LIMIT
        )
        chunks = [_chunk_from_item(item, score=0.0) for item in items]
        return ToolResult(evidence=chunks, candidates=len(chunks))


class CompareDocumentsTool(Tool):
    name = "compare_documents"
    description = (
        "Compare information across two or more documents. Use when the user asks to "
        "compare plans, requirements, or features between named documents."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "documents": {"type": "array"},
            "question": {"type": "string"},
        },
        "required": ["documents", "question"],
    }

    def __init__(self, retriever):
        self._retriever = retriever

    async def execute(self, context: ToolContext, arguments: dict) -> ToolResult:
        requested = arguments["documents"]
        question = arguments["question"]
        resolved = [
            document
            for name in requested
            if (document := _resolve_document(context.documents, name))
        ]
        missing = [
            name
            for name in requested
            if all(document["name"] != name for document in resolved)
        ]

        top_k = max(1, TOOL_SEARCH_TOP_K // len(requested))
        evidence: list[RetrievedChunk] = []
        for document in resolved:
            evidence.extend(
                self._retriever.search_in_document(
                    context.knowledge_base_id,
                    question,
                    document["id"],
                    top_k=top_k + 1,
                )
            )

        if not resolved:
            return ToolResult(
                summary=(
                    f"None of the requested documents were found: {', '.join(missing)}."
                )
            )

        note = f"Requested documents not found: {', '.join(missing)}." if missing else None
        return ToolResult(evidence=evidence, summary=note, candidates=len(evidence))


class GetConversationContextTool(Tool):
    name = "get_conversation_context"
    description = (
        "Recall the most relevant parts of the current conversation. Use when the user "
        "refers to an earlier discussion (\"what did we say about X\", \"that document\", "
        "\"the one we discussed\")."
    )
    input_schema = {
        "type": "object",
        "properties": {"question": {"type": "string"}},
        "required": ["question"],
    }

    async def execute(self, context: ToolContext, arguments: dict) -> ToolResult:
        if not context.conversation_id or not context.memory_store:
            return ToolResult(summary="No prior conversation is available.")
        if not context.memory_selector:
            return ToolResult(summary="Conversation recall is unavailable.")
        messages = context.memory_store.list_messages(context.conversation_id)
        selected = context.memory_selector.select(messages, arguments["question"])
        if not selected:
            return ToolResult(
                summary="No relevant parts of the conversation were found."
            )
        return ToolResult(
            evidence=[],
            summary="\n".join(
                f"{message['role']}: {message['content']}" for message in selected
            ),
        )


def _chunk_from_item(item: dict, score: float) -> RetrievedChunk:
    return RetrievedChunk(
        text=item["text"],
        chunk_id=item["chunk_id"],
        document_id=item["document_id"],
        document_name=item["document_name"],
        page=item["page"],
        section=item["section"],
        score=score,
    )