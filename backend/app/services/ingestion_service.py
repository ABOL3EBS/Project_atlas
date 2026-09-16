import hashlib
import re
from pathlib import Path

from app.embeddings.base import EmbeddingProvider
from app.ingestion import (
    SUPPORTED_EXTENSIONS,
    ChunkingConfig,
    UnsupportedFormatError,
    chunk_document,
    parse_document,
)
from app.retrieval.base import VectorStore

from .document_store import DocumentStore

_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_filename(name: str) -> str:
    name = Path(name).name
    name = _SAFE_NAME_RE.sub("_", name)
    return name.strip("._")


class IngestionService:
    def __init__(
        self,
        vector_store: VectorStore,
        embedding_provider: EmbeddingProvider,
        document_store: DocumentStore,
        chunking_config: ChunkingConfig,
        max_upload_size: int,
    ):
        self._vector_store = vector_store
        self._embedding_provider = embedding_provider
        self._document_store = document_store
        self._chunking_config = chunking_config
        self._max_upload_size = max_upload_size

    def ingest(self, knowledge_base_id: str, filename: str, content: bytes) -> dict:
        self._validate(filename, content)
        sha256 = hashlib.sha256(content).hexdigest()
        existing = self._document_store.find_existing(knowledge_base_id, sha256)
        if existing and existing["status"] == "indexed":
            return existing

        document_id = self._document_store.create(knowledge_base_id, filename, len(content), sha256)
        try:
            pages = parse_document(filename, content)
            if not pages:
                raise ValueError("No extractable text found in document")
            chunks = chunk_document(document_id, filename, pages, self._chunking_config)
            if not chunks:
                raise ValueError("Document produced no chunks")
            embeddings = self._embedding_provider.embed_documents([chunk.text for chunk in chunks])
            self._vector_store.add_chunks(knowledge_base_id, chunks, embeddings)
            self._document_store.mark_indexed(document_id, len(chunks))
            return self._document_store.get(knowledge_base_id, document_id)
        except Exception as error:
            self._document_store.mark_failed(document_id, str(error))
            raise

    def delete(self, knowledge_base_id: str, document_id: str) -> bool:
        deleted = self._document_store.delete(knowledge_base_id, document_id)
        if deleted:
            self._vector_store.delete_document(knowledge_base_id, document_id)
        return deleted

    def list(self, knowledge_base_id: str) -> list[dict]:
        return self._document_store.list(knowledge_base_id)

    def _validate(self, filename: str, content: bytes) -> None:
        extension = Path(filename).suffix.lower()
        if extension not in SUPPORTED_EXTENSIONS:
            raise UnsupportedFormatError(f"Unsupported format: {extension}")
        if not content:
            raise ValueError("Empty file")
        if len(content) > self._max_upload_size:
            raise ValueError(f"File exceeds {self._max_upload_size} bytes")