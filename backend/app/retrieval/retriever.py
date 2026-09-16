from dataclasses import dataclass

from app.embeddings.base import EmbeddingProvider

from .base import VectorStore


@dataclass
class RetrievedChunk:
    text: str
    chunk_id: str
    document_id: str
    document_name: str
    page: int | None
    section: str | None
    score: float


class Retriever:
    def __init__(
        self,
        vector_store: VectorStore,
        embedding_provider: EmbeddingProvider,
        top_k: int = 8,
        min_score: float = 0.20,
    ):
        self._vector_store = vector_store
        self._embedding_provider = embedding_provider
        self._top_k = top_k
        self._min_score = min_score

    def search(self, knowledge_base_id: str, query: str) -> list[RetrievedChunk]:
        query_embedding = self._embedding_provider.embed_query(query)
        raw = self._vector_store.query(
            knowledge_base_id, query_embedding, top_k=self._top_k, min_score=self._min_score
        )
        results = [
            RetrievedChunk(
                text=item["text"],
                chunk_id=item["chunk_id"],
                document_id=item["document_id"],
                document_name=item["document_name"],
                page=item["page"],
                section=item["section"],
                score=item["score"],
            )
            for item in raw
        ]
        return [item for item in results if item.score >= self._min_score]