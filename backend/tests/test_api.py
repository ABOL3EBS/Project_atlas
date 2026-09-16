import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_chat_service, get_ingestion_service, get_settings
from app.config import Settings
from app.ingestion import ChunkingConfig
from app.main import app
from app.retrieval.retriever import Retriever
from app.services.chat_service import ChatService
from app.services.document_store import DocumentStore
from app.services.ingestion_service import IngestionService
from tests.conftest import (
    FakeEmbeddingProvider,
    FakeLLMProvider,
    FakeVectorStore,
)


@pytest.fixture()
def services(tmp_path: Path):
    vector_store = FakeVectorStore()
    embeddings = FakeEmbeddingProvider()
    document_store = DocumentStore(str(tmp_path / "atlas.db"))
    ingestion = IngestionService(
        vector_store=vector_store,
        embedding_provider=embeddings,
        document_store=document_store,
        chunking_config=ChunkingConfig(chunk_size=50, chunk_overlap=5),
        max_upload_size=1024 * 1024,
    )
    retriever = Retriever(vector_store=vector_store, embedding_provider=embeddings)
    chat_service = ChatService(retriever=retriever, llm_provider=FakeLLMProvider())

    def override_settings() -> Settings:
        return Settings(
            sqlite_path=str(tmp_path / "atlas.db"),
            chroma_dir=str(tmp_path / "chroma"),
        )

    app.dependency_overrides[get_settings] = override_settings
    app.dependency_overrides[get_ingestion_service] = lambda: ingestion
    app.dependency_overrides[get_chat_service] = lambda: chat_service
    yield chat_service
    app.dependency_overrides.clear()


@pytest.fixture()
def client(services):
    with TestClient(app) as test_client:
        yield test_client


def test_upload_and_list(client, services):
    response = client.post(
        "/api/documents/upload",
        files={"file": ("notes.txt", b"Atlas retrieves evidence.\n\nIt answers questions.")},
        data={"knowledge_base_id": "kb-a"},
    )
    assert response.status_code == 201
    document = response.json()
    assert document["status"] == "indexed"
    assert document["knowledge_base_id"] == "kb-a"

    listing = client.get("/api/documents", params={"knowledge_base_id": "kb-a"})
    assert [doc["id"] for doc in listing.json()] == [document["id"]]


def _replace_default_retriever(chat_service: ChatService, vector_store: FakeVectorStore):
    retriever = Retriever(
        vector_store=vector_store, embedding_provider=FakeEmbeddingProvider()
    )
    replacement = ChatService(retriever=retriever, llm_provider=FakeLLMProvider())
    app.dependency_overrides[get_chat_service] = lambda: replacement
    return replacement


def test_knowledge_base_isolation(client, services):
    client.post(
        "/api/documents/upload",
        files={"file": ("a.txt", b"private to kb-a")},
        data={"knowledge_base_id": "kb-a"},
    )
    other = client.get("/api/documents", params={"knowledge_base_id": "kb-b"})
    assert other.json() == []


def test_upload_rejects_unsupported_format(client, services):
    response = client.post(
        "/api/documents/upload",
        files={"file": ("evil.exe", b"MZ")},
    )
    assert response.status_code == 400
    assert "Unsupported format" in response.json()["detail"]


def test_upload_malformed_pdf_returns_400_and_records_failure(client, services):
    response = client.post(
        "/api/documents/upload",
        files={"file": ("broken.pdf", b"not a real pdf")},
        data={"knowledge_base_id": "kb-a"},
    )
    assert response.status_code == 400
    assert "Could not parse PDF" in response.json()["detail"]

    listing = client.get("/api/documents", params={"knowledge_base_id": "kb-a"})
    assert listing.json()[0]["status"] == "failed"


def test_chat_provider_failure_emits_error_event(client, services):
    class ExplodingRetriever:
        def search(self, knowledge_base_id: str, query: str):
            raise RuntimeError("vector store unavailable")

    replacement = ChatService(
        retriever=ExplodingRetriever(), llm_provider=FakeLLMProvider()
    )
    app.dependency_overrides[get_chat_service] = lambda: replacement

    response = client.post(
        "/api/chat", json={"message": "anything", "knowledge_base_id": "kb-a"}
    )
    events = _parse_sse(response.text)
    errors = [event for event in events if event["type"] == "error"]
    assert errors
    assert "vector store unavailable" in errors[0]["message"]


def test_delete_document(client, services):
    document = client.post(
        "/api/documents/upload",
        files={"file": ("a.txt", b"content")},
    ).json()
    response = client.delete(f"/api/documents/{document['id']}")
    assert response.status_code == 204
    assert client.delete(f"/api/documents/{document['id']}").status_code == 404


def test_chat_streams_events_and_answer(client, services):
    vector_store = FakeVectorStore()
    vector_store.query_results = [
        {
            "chunk_id": "doc-1-0",
            "text": "On-premise deployment is documented.",
            "document_id": "doc-1",
            "document_name": "install.pdf",
            "page": 18,
            "section": None,
            "score": 0.85,
        }
    ]
    _replace_default_retriever(services, vector_store)

    response = client.post(
        "/api/chat", json={"message": "deploy on-premise?", "knowledge_base_id": "kb-a"}
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    events = _parse_sse(response.text)
    assert any(event["type"] == "retrieval" and event["count"] == 1 for event in events)
    tokens = "".join(event["text"] for event in events if event["type"] == "token")
    assert tokens == "The system works."
    assert any(event["type"] == "done" for event in events)


def test_chat_reports_when_no_evidence(client, services):
    class NoResultsRetriever:
        def search(self, knowledge_base_id: str, query: str):
            return []

    replacement = ChatService(
        retriever=NoResultsRetriever(), llm_provider=FakeLLMProvider()
    )
    app.dependency_overrides[get_chat_service] = lambda: replacement

    response = client.post(
        "/api/chat", json={"message": "totally unknown", "knowledge_base_id": "kb-a"}
    )
    events = _parse_sse(response.text)
    assert any(
        event["type"] == "answer" and "No relevant information" in event["text"]
        for event in events
    )
    assert all(event["type"] != "token" for event in events)


def test_health_reports_availability(client, services):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] in {"ok", "degraded"}


def _parse_sse(text: str) -> list[dict]:
    events = []
    for block in text.split("\n\n"):
        if not block.strip():
            continue
        event_type = "message"
        data_lines = []
        for line in block.split("\n"):
            if line.startswith("event:"):
                event_type = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                data_lines.append(line.split(":", 1)[1].strip())
        payload = json.loads("\n".join(data_lines))
        payload["type"] = event_type
        events.append(payload)
    return events