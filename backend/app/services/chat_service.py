from collections.abc import AsyncIterator

from app.agent.agent import AtlasAgent
from app.agent.grounding import (
    DIRECT_ANSWER_PROMPT,
    NOT_FOUND_MESSAGE,
    SYSTEM_PROMPT,
    Citation,
    build_citations,
    build_prompt,
    build_prompt_with_memory,
    chunk_briefs,
    verify_citations,
)
from app.agent.registry import ToolRegistry
from app.agent.tools import (
    CompareDocumentsTool,
    GetConversationContextTool,
    RetrieveDocumentTool,
    SearchKnowledgeBaseTool,
)
from app.config import get_settings
from app.embeddings import OllamaEmbeddingProvider
from app.llm.base import LLMProvider
from app.memory.conversation_store import ConversationStore
from app.memory.selector import MemorySelector
from app.retrieval.base import VectorStore
from app.retrieval.retriever import Retriever
from app.services.document_store import DocumentStore

DEFAULT_RETRIEVE_LIMIT = 12


class ChatService:
    def __init__(
        self,
        retriever: Retriever,
        llm_provider: LLMProvider,
        grounding_threshold: float = 0.45,
        *,
        vector_store: VectorStore | None = None,
        document_store: DocumentStore | None = None,
        conversation_store: ConversationStore | None = None,
        memory_selector: MemorySelector | None = None,
        registry: ToolRegistry | None = None,
    ):
        settings = get_settings()
        self._retriever = retriever
        self._llm_provider = llm_provider
        self._grounding_threshold = grounding_threshold

        self._vector_store = vector_store or _default_vector_store(settings)
        self._document_store = document_store or DocumentStore(settings.sqlite_path)
        self._conversation_store = conversation_store
        self._memory_selector = memory_selector or _default_memory_selector(settings)
        self._registry = registry or _default_registry(
            retriever, self._vector_store
        )

        self._agent = AtlasAgent(
            retriever=retriever,
            llm_provider=llm_provider,
            vector_store=self._vector_store,
            document_store=self._document_store,
            conversation_store=self._conversation_store,
            memory_selector=self._memory_selector,
            registry=self._registry,
            grounding_threshold=grounding_threshold,
        )

    async def run(
        self,
        knowledge_base_id: str,
        question: str,
        conversation_id: str | None = None,
    ) -> AsyncIterator[dict]:
        async for event in self._agent.run(knowledge_base_id, question, conversation_id):
            yield event

    async def _run_inner(self, knowledge_base_id: str, question: str) -> AsyncIterator[dict]:
        async for event in self._agent.run(knowledge_base_id, question, None):
            yield event


def _default_vector_store(settings) -> VectorStore:
    from app.retrieval.chroma_store import ChromaVectorStore
    return ChromaVectorStore(settings.chroma_dir)


def _default_memory_selector(settings) -> MemorySelector:
    embedding_provider = OllamaEmbeddingProvider(
        settings.ollama_base_url, settings.embedding_model
    )
    return MemorySelector(embedding_provider)


def _default_registry(retriever: Retriever, vector_store: VectorStore) -> ToolRegistry:
    return ToolRegistry(
        [
            SearchKnowledgeBaseTool(retriever),
            RetrieveDocumentTool(retriever, vector_store),
            CompareDocumentsTool(retriever),
            GetConversationContextTool(),
        ]
    )


__all__ = [
    "DIRECT_ANSWER_PROMPT",
    "NOT_FOUND_MESSAGE",
    "SYSTEM_PROMPT",
    "ChatService",
    "Citation",
    "build_citations",
    "build_prompt",
    "build_prompt_with_memory",
    "chunk_briefs",
    "verify_citations",
]