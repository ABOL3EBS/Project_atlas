import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.deps import (
    get_chat_service,
    get_conversation_store,
    get_ingestion_service,
    get_settings,
)
from app.config import Settings
from app.ingestion import ChunkingConfig
from app.main import app
from app.memory.conversation_store import ConversationStore
from app.retrieval.retriever import Retriever
from app.services.chat_service import ChatService
from app.services.document_store import DocumentStore
from app.services.ingestion_service import IngestionService
from tests.conftest import (
    FakeEmbeddingProvider,
    FakeLLMProvider,
    FakeVectorStore,
)

SEARCH_PLAN = '{"tool": "search_knowledge_base", "arguments": {"query": "query", "top_k": 4}}'


@pytest.fixture()
def services(tmp_path: Path):
    vector_store = FakeVectorStore()
    embeddings = FakeEmbeddingProvider()
    document_store = DocumentStore(str(tmp_path / "atlas.db"))
    conversation_store = ConversationStore(str(tmp_path / "conversations.db"))
    ingestion = IngestionService(
        vector_store=vector_store,
        embedding_provider=embeddings,
        document_store=document_store,
        chunking_config=ChunkingConfig(chunk_size=50, chunk_overlap=5),
        max_upload_size=1024 * 1024,
    )
    retriever = Retriever(vector_store=vector_store, embedding_provider=embeddings)
    chat_service = ChatService(
        retriever=retriever,
        llm_provider=FakeLLMProvider(),
        vector_store=vector_store,
        document_store=document_store,
        conversation_store=conversation_store,
    )

    def override_settings() -> Settings:
        return Settings(
            sqlite_path=str(tmp_path / "atlas.db"),
            chroma_dir=str(tmp_path / "chroma"),
            conversation_db_path=str(tmp_path / "conversations.db"),
        )

    app.dependency_overrides[get_settings] = override_settings
    app.dependency_overrides[get_ingestion_service] = lambda: ingestion
    app.dependency_overrides[get_chat_service] = lambda: chat_service
    app.dependency_overrides[get_conversation_store] = lambda: conversation_store
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
    replacement = ChatService(
        retriever=retriever,
        llm_provider=FakeLLMProvider(plan_response=SEARCH_PLAN),
        vector_store=vector_store,
        document_store=chat_service._document_store,
    )
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
        def search(self, knowledge_base_id: str, query: str, top_k: int | None = None):
            raise RuntimeError("vector store unavailable")

    replacement = ChatService(
        retriever=ExplodingRetriever(),
        llm_provider=FakeLLMProvider(plan_response=SEARCH_PLAN),
        vector_store=FakeVectorStore(),
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
        def search(self, knowledge_base_id: str, query: str, top_k: int | None = None):
            return []

    replacement = ChatService(
        retriever=NoResultsRetriever(),
        llm_provider=FakeLLMProvider(plan_response=SEARCH_PLAN),
        vector_store=FakeVectorStore(),
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


def test_chat_returns_and_persists_conversation(client, services):
    response = client.post(
        "/api/chat",
        json={"message": "greetings", "knowledge_base_id": "kb-a"},
    )
    events = _parse_sse(response.text)
    conversation_events = [e for e in events if e["type"] == "conversation"]
    assert conversation_events
    conversation_id = conversation_events[0]["conversation_id"]
    assert conversation_id

    detail = client.get(
        f"/api/conversations/{conversation_id}",
        params={"knowledge_base_id": "kb-a"},
    )
    assert detail.status_code == 200
    assert detail.json()["messages"][0]["role"] == "user"
    assert detail.json()["messages"][-1]["role"] == "assistant"


def test_conversation_list_isolated_by_knowledge_base(client, services):
    client.post("/api/chat", json={"message": "one", "knowledge_base_id": "kb-a"})
    client.post("/api/chat", json={"message": "two", "knowledge_base_id": "kb-b"})

    kb_a = client.get("/api/conversations", params={"knowledge_base_id": "kb-a"})
    kb_b = client.get("/api/conversations", params={"knowledge_base_id": "kb-b"})
    assert len(kb_a.json()) == 1
    assert len(kb_b.json()) == 1


def test_conversation_reuse_resumes_same_thread(client, services):
    first = client.post(
        "/api/chat", json={"message": "first", "knowledge_base_id": "kb-a"}
    )
    conversation_id = next(
        e["conversation_id"]
        for e in _parse_sse(first.text)
        if e["type"] == "conversation"
    )

    second = client.post(
        "/api/chat",
        json={
            "message": "second",
            "knowledge_base_id": "kb-a",
            "conversation_id": conversation_id,
        },
    )
    resumed_id = next(
        e["conversation_id"]
        for e in _parse_sse(second.text)
        if e["type"] == "conversation"
    )
    assert resumed_id == conversation_id

    detail = client.get(
        f"/api/conversations/{conversation_id}",
        params={"knowledge_base_id": "kb-a"},
    )
    roles = [message["role"] for message in detail.json()["messages"]]
    assert roles.count("user") == 2


def test_conversation_detail_is_knowledge_base_scoped(client, services):
    response = client.post(
        "/api/chat", json={"message": "hello", "knowledge_base_id": "kb-a"}
    )
    conversation_id = next(
        e["conversation_id"]
        for e in _parse_sse(response.text)
        if e["type"] == "conversation"
    )

    wrong_kb = client.get(
        f"/api/conversations/{conversation_id}",
        params={"knowledge_base_id": "kb-other"},
    )
    assert wrong_kb.status_code == 404


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