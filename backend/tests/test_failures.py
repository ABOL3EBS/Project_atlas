import httpx
import pytest

from app.embeddings import OllamaEmbeddingProvider
from app.embeddings import ollama_provider as embedding_provider_module
from app.llm import OllamaProvider
from app.llm import ollama_provider as llm_provider_module
from app.retrieval.retriever import RetrievedChunk
from app.services.chat_service import ChatService
from tests.conftest import FakeLLMProvider


class ExplodingRetriever:
    def __init__(self, error: Exception):
        self._error = error

    def search(self, knowledge_base_id: str, query: str) -> list[RetrievedChunk]:
        raise self._error


class RaisingLLM:
    async def stream(self, prompt: str, *, system: str | None = None):
        raise RuntimeError("llm generation failed")
        yield  # pragma: no cover - marks this as an async generator


class StubRetriever:
    def __init__(self, chunks: list[RetrievedChunk]):
        self._chunks = chunks

    def search(self, knowledge_base_id: str, query: str) -> list[RetrievedChunk]:
        return self._chunks


def _chunk(score: float = 0.9) -> RetrievedChunk:
    return RetrievedChunk(
        text="evidence",
        chunk_id="c-1",
        document_id="d-1",
        document_name="a.md",
        page=None,
        section=None,
        score=score,
    )


async def _events(service: ChatService) -> list[dict]:
    return [event async for event in service.run("kb-a", "question")]


async def test_embedding_failure_emits_controlled_error_event():
    service = ChatService(
        ExplodingRetriever(RuntimeError("embedding service down")), FakeLLMProvider()
    )
    events = await _events(service)
    errors = [event for event in events if event["type"] == "error"]
    assert errors
    assert "embedding service down" in errors[0]["message"]


async def test_vector_store_failure_emits_controlled_error_event():
    service = ChatService(
        ExplodingRetriever(RuntimeError("chroma unavailable")), FakeLLMProvider()
    )
    events = await _events(service)
    assert any(event["type"] == "error" for event in events)


async def test_llm_failure_emits_controlled_error_event():
    service = ChatService(StubRetriever([_chunk()]), RaisingLLM())
    events = await _events(service)
    errors = [event for event in events if event["type"] == "error"]
    assert errors
    assert "llm generation failed" in errors[0]["message"]


def test_embedding_provider_check_false_when_unreachable(monkeypatch):
    def _boom(*args, **kwargs):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(embedding_provider_module.httpx, "get", _boom)
    provider = OllamaEmbeddingProvider("http://localhost:1", "nomic-embed-text")
    assert provider.check() is False


def test_llm_provider_check_false_when_unreachable(monkeypatch):
    def _boom(*args, **kwargs):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(llm_provider_module.httpx, "get", _boom)
    provider = OllamaProvider("http://localhost:1", "gemma2")
    assert provider.check() is False


def test_embedding_request_failure_propagates(monkeypatch):
    def _boom(*args, **kwargs):
        raise httpx.ConnectError("embedding endpoint down")

    monkeypatch.setattr(embedding_provider_module.httpx, "post", _boom)
    provider = OllamaEmbeddingProvider("http://localhost:1", "nomic-embed-text")
    with pytest.raises(httpx.ConnectError):
        provider.embed_query("hello")