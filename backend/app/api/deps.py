from functools import lru_cache

from app.config import get_settings
from app.embeddings import EmbeddingProvider, OllamaEmbeddingProvider
from app.ingestion import ChunkingConfig
from app.llm import LLMProvider, OllamaProvider
from app.memory.conversation_store import ConversationStore
from app.memory.selector import MemorySelector
from app.retrieval import ChromaVectorStore, VectorStore
from app.retrieval.retriever import Retriever
from app.services.chat_service import ChatService
from app.services.document_store import DocumentStore
from app.services.ingestion_service import IngestionService


@lru_cache
def get_vector_store() -> VectorStore:
    settings = get_settings()
    return ChromaVectorStore(settings.chroma_dir)


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()
    if settings.embedding_provider == "ollama":
        return OllamaEmbeddingProvider(settings.ollama_base_url, settings.embedding_model)
    raise ValueError(f"Unknown embedding provider: {settings.embedding_provider}")


@lru_cache
def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    if settings.llm_provider == "ollama":
        return OllamaProvider(settings.ollama_base_url, settings.llm_model)
    raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")


def get_document_store() -> DocumentStore:
    settings = get_settings()
    return DocumentStore(settings.sqlite_path)


def get_conversation_store() -> ConversationStore:
    settings = get_settings()
    return ConversationStore(settings.conversation_db_path)


def get_memory_selector() -> MemorySelector:
    settings = get_settings()
    embedding_provider = OllamaEmbeddingProvider(
        settings.ollama_base_url, settings.embedding_model
    )
    return MemorySelector(embedding_provider)


def get_ingestion_service() -> IngestionService:
    settings = get_settings()
    return IngestionService(
        vector_store=get_vector_store(),
        embedding_provider=get_embedding_provider(),
        document_store=get_document_store(),
        chunking_config=ChunkingConfig(settings.chunk_size, settings.chunk_overlap),
        max_upload_size=settings.max_upload_size,
    )


def get_chat_service() -> ChatService:
    settings = get_settings()
    retriever = Retriever(
        vector_store=get_vector_store(),
        embedding_provider=get_embedding_provider(),
        top_k=settings.retrieval_top_k,
        min_score=settings.retrieval_min_score,
    )
    return ChatService(
        retriever=retriever,
        llm_provider=get_llm_provider(),
        grounding_threshold=settings.grounding_threshold,
        vector_store=get_vector_store(),
        document_store=get_document_store(),
        conversation_store=get_conversation_store(),
        memory_selector=get_memory_selector(),
    )