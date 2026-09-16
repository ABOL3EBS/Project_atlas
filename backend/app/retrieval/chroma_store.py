import re

import chromadb

from app.ingestion.chunking import Chunk

from .base import VectorStore


class ChromaVectorStore(VectorStore):
    def __init__(self, persist_dir: str):
        self._client = chromadb.PersistentClient(path=persist_dir)
        self._collections: dict[str, chromadb.Collection] = {}

    def add_chunks(
        self, knowledge_base_id: str, chunks: list[Chunk], embeddings: list[list[float]]
    ) -> None:
        collection = self._collection(knowledge_base_id)
        collection.upsert(
            ids=[chunk.chunk_id for chunk in chunks],
            documents=[chunk.text for chunk in chunks],
            embeddings=embeddings,
            metadatas=[
                {
                    "document_id": chunk.document_id,
                    "document_name": chunk.document_name,
                    "page": chunk.page if chunk.page is not None else -1,
                    "section": chunk.section or "",
                }
                for chunk in chunks
            ],
        )

    def query(
        self,
        knowledge_base_id: str,
        embedding: list[float],
        top_k: int,
        min_score: float | None = None,
    ) -> list[dict]:
        collection = self._collection(knowledge_base_id)
        result = collection.query(
            query_embeddings=[embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
        return self._format_results(result, min_score)

    def delete_document(self, knowledge_base_id: str, document_id: str) -> None:
        collection = self._collection(knowledge_base_id)
        collection.delete(where={"document_id": document_id})

    def document_chunk_count(self, knowledge_base_id: str, document_id: str) -> int:
        collection = self._collection(knowledge_base_id)
        result = collection.get(
            where={"document_id": document_id}, include=["metadatas"]
        )
        return len(result["ids"])

    def count(self, knowledge_base_id: str) -> int:
        collection = self._collection(knowledge_base_id)
        return collection.count()

    def _collection(self, knowledge_base_id: str) -> chromadb.Collection:
        name = _collection_name(knowledge_base_id)
        if name not in self._collections:
            self._collections[name] = self._client.get_or_create_collection(
                name=name, metadata={"hnsw:space": "cosine"}
            )
        return self._collections[name]

    def _format_results(self, result: dict, min_score: float | None) -> list[dict]:
        ids = result.get("ids", [[]])[0]
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]

        formatted = []
        for chunk_id, document, metadata, distance in zip(
            ids, documents, metadatas, distances, strict=True
        ):
            score = 1.0 - float(distance)
            if min_score is not None and score < min_score:
                continue
            page = metadata.get("page")
            if page is None or page < 0:
                page_marker = None
            else:
                page_marker = int(page)
            formatted.append(
                {
                    "chunk_id": chunk_id,
                    "text": document,
                    "document_id": metadata.get("document_id", ""),
                    "document_name": metadata.get("document_name", ""),
                    "page": page_marker,
                    "section": metadata.get("section") or None,
                    "score": score,
                }
            )
        return formatted


def _collection_name(knowledge_base_id: str) -> str:
    sanitized = re.sub(r"[^a-zA-Z0-9_-]", "_", knowledge_base_id)
    return f"kb_{sanitized}"[:63]