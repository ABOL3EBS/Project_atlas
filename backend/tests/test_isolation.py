from pathlib import Path

from app.ingestion import ChunkingConfig
from app.retrieval import ChromaVectorStore
from app.retrieval.retriever import Retriever
from app.services.document_store import DocumentStore
from app.services.ingestion_service import IngestionService
from tests.conftest import FakeEmbeddingProvider


def _setup(tmp_path: Path) -> tuple[IngestionService, Retriever]:
    embeddings = FakeEmbeddingProvider(dimension=8)
    vector_store = ChromaVectorStore(str(tmp_path / "chroma"))
    service = IngestionService(
        vector_store=vector_store,
        embedding_provider=embeddings,
        document_store=DocumentStore(str(tmp_path / "atlas.db")),
        chunking_config=ChunkingConfig(chunk_size=50, chunk_overlap=5),
        max_upload_size=1024 * 1024,
    )
    retriever = Retriever(vector_store=vector_store, embedding_provider=embeddings, top_k=10)
    return service, retriever


def test_knowledge_bases_are_isolated_at_retrieval(tmp_path):
    service, retriever = _setup(tmp_path)

    doc_a = service.ingest("kb-a", "a.txt", b"This document only describes the ALPHA subsystem.")
    doc_b = service.ingest("kb-b", "b.txt", b"This document only describes the BETA subsystem.")

    results_a = retriever.search("kb-a", "describe the subsystem")
    results_b = retriever.search("kb-b", "describe the subsystem")

    assert results_a
    assert results_b
    assert all(result.document_id == doc_a["id"] for result in results_a)
    assert all(result.document_id == doc_b["id"] for result in results_b)

    ids_a = {result.chunk_id for result in results_a}
    ids_b = {result.chunk_id for result in results_b}
    assert ids_a.isdisjoint(ids_b)


def test_empty_knowledge_base_returns_no_results(tmp_path):
    service, retriever = _setup(tmp_path)
    service.ingest("kb-a", "a.txt", b"content in the other knowledge base")

    assert retriever.search("kb-b", "content") == []