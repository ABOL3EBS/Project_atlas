from app.retrieval.retriever import Retriever
from tests.conftest import FakeEmbeddingProvider, FakeVectorStore


def test_search_returns_scoped_retrieved_chunks():
    vector_store = FakeVectorStore()
    vector_store.query_results = [
        {
            "chunk_id": "doc-1-0",
            "text": "Atlas supports on-premise deployment.",
            "document_id": "doc-1",
            "document_name": "installation.md",
            "page": 5,
            "section": "Deployment",
            "score": 0.81,
        }
    ]
    embeddings = FakeEmbeddingProvider()
    retriever = Retriever(vector_store=vector_store, embedding_provider=embeddings, top_k=4)

    results = retriever.search("kb-a", "can I deploy on-premise?")

    assert len(results) == 1
    assert results[0].document_name == "installation.md"
    assert results[0].page == 5
    assert results[0].section == "Deployment"
    assert results[0].score == 0.81
    assert embeddings.embedded_queries == ["can I deploy on-premise?"]


def test_search_applies_min_score_filter():
    vector_store = FakeVectorStore()
    vector_store.query_results = [
        {
            "chunk_id": "doc-1-0",
            "text": "low relevance",
            "document_id": "doc-1",
            "document_name": "a.md",
            "page": None,
            "section": None,
            "score": 0.05,
        }
    ]
    retriever = Retriever(
        vector_store=vector_store,
        embedding_provider=FakeEmbeddingProvider(),
        min_score=0.20,
    )

    assert retriever.search("kb-a", "anything") == []


def test_search_returns_empty_when_no_results():
    vector_store = FakeVectorStore()
    retriever = Retriever(
        vector_store=vector_store, embedding_provider=FakeEmbeddingProvider()
    )
    assert retriever.search("kb-a", "anything") == []