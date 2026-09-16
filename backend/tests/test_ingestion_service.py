from pathlib import Path

import pytest

from app.ingestion import ChunkingConfig, UnsupportedFormatError
from app.services.document_store import DocumentStore
from app.services.ingestion_service import IngestionService, sanitize_filename
from tests.conftest import FakeEmbeddingProvider, FakeVectorStore, make_pdf


def _make_service(
    tmp_path: Path,
    max_upload_size: int = 1024 * 1024,
) -> tuple[IngestionService, FakeVectorStore, FakeEmbeddingProvider]:
    vector_store = FakeVectorStore()
    embeddings = FakeEmbeddingProvider()
    service = IngestionService(
        vector_store=vector_store,
        embedding_provider=embeddings,
        document_store=DocumentStore(str(tmp_path / "atlas.db")),
        chunking_config=ChunkingConfig(chunk_size=50, chunk_overlap=5),
        max_upload_size=max_upload_size,
    )
    return service, vector_store, embeddings


def test_ingest_txt_indexes_chunks(tmp_path):
    service, vector_store, _ = _make_service(tmp_path)
    content = b"Atlas is a RAG system.\n\nIt retrieves evidence."
    document = service.ingest("kb-a", "notes.txt", content)
    assert document["status"] == "indexed"
    assert document["chunk_count"] == 1
    assert vector_store.chunks[0][0] == "kb-a"


def test_ingest_pdf_extracts_text(tmp_path):
    service, vector_store, _ = _make_service(tmp_path)
    pdf = make_pdf("On-premise deployment is supported here.")
    document = service.ingest("kb-a", "install.pdf", pdf)
    assert document["status"] == "indexed"
    assert vector_store.chunks[0][1].page == 1
    assert "On-premise" in vector_store.chunks[0][1].text


def test_ingest_dedupes_by_content_hash(tmp_path):
    service, _, _ = _make_service(tmp_path)
    content = b"identical content"
    first = service.ingest("kb-a", "a.txt", content)
    second = service.ingest("kb-a", "b.txt", content)
    assert first["id"] == second["id"]


def test_empty_file_rejected(tmp_path):
    service, _, _ = _make_service(tmp_path)
    with pytest.raises(ValueError, match="Empty file"):
        service.ingest("kb-a", "empty.txt", b"")


def test_unsupported_format_rejected(tmp_path):
    service, _, _ = _make_service(tmp_path)
    with pytest.raises(UnsupportedFormatError):
        service.ingest("kb-a", "evil.exe", b"MZ")


def test_oversized_upload_rejected(tmp_path):
    service, _, _ = _make_service(tmp_path, max_upload_size=16)
    with pytest.raises(ValueError, match="exceeds"):
        service.ingest("kb-a", "big.txt", b"x" * 100)


def test_malformed_pdf_rejected(tmp_path):
    service, _, _ = _make_service(tmp_path)
    with pytest.raises(ValueError, match="Could not parse PDF"):
        service.ingest("kb-a", "broken.pdf", b"this is not a real pdf")


def test_pdf_with_no_text_rejected(tmp_path):
    service, _, _ = _make_service(tmp_path)
    with pytest.raises(ValueError, match="No extractable text"):
        service.ingest("kb-a", "empty.pdf", make_pdf(""))


def test_whitespace_only_txt_rejected(tmp_path):
    service, _, _ = _make_service(tmp_path)
    with pytest.raises(ValueError, match="No extractable text|produced no chunks"):
        service.ingest("kb-a", "blank.txt", b"   \n\n   ")


def test_failed_upload_leaves_failed_record_not_stuck(tmp_path):
    service, _, _ = _make_service(tmp_path)
    with pytest.raises(ValueError):
        service.ingest("kb-a", "broken.pdf", b"not a pdf")
    records = service.list("kb-a")
    assert len(records) == 1
    assert records[0]["status"] == "failed"


def test_delete_removes_vectors_and_record(tmp_path):
    service, vector_store, _ = _make_service(tmp_path)
    document = service.ingest("kb-a", "a.txt", b"content")
    assert service.delete("kb-a", document["id"]) is True
    assert ("kb-a", document["id"]) in vector_store.deleted
    assert service.list("kb-a") == []


def test_failed_ingest_records_error(tmp_path):
    service, vector_store, _ = _make_service(tmp_path)

    def _boom(*args, **kwargs):
        raise RuntimeError("embedding store down")

    vector_store.add_chunks = _boom
    with pytest.raises(RuntimeError):
        service.ingest("kb-a", "a.txt", b"content")
    records = service.list("kb-a")
    assert records[0]["status"] == "failed"
    assert "embedding store down" in records[0]["error"]


def test_sanitize_filename():
    assert sanitize_filename("../../etc/passwd") == "passwd"
    assert sanitize_filename("My Doc (2).txt") == "My_Doc_2_.txt"
    assert sanitize_filename("clean.txt") == "clean.txt"