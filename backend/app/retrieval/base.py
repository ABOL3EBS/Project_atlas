from abc import ABC, abstractmethod

from app.ingestion.chunking import Chunk


class VectorStore(ABC):
    @abstractmethod
    def add_chunks(
        self, knowledge_base_id: str, chunks: list[Chunk], embeddings: list[list[float]]
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def query(
        self,
        knowledge_base_id: str,
        embedding: list[float],
        top_k: int,
        min_score: float | None = None,
        where: dict | None = None,
    ) -> list[dict]:
        raise NotImplementedError

    @abstractmethod
    def get_document_chunks(
        self, knowledge_base_id: str, document_id: str, limit: int = 12
    ) -> list[dict]:
        raise NotImplementedError

    @abstractmethod
    def delete_document(self, knowledge_base_id: str, document_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def document_chunk_count(self, knowledge_base_id: str, document_id: str) -> int:
        raise NotImplementedError