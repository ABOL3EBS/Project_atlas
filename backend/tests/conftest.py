import pymupdf

from app.embeddings.base import EmbeddingProvider
from app.llm.base import LLMProvider
from app.retrieval.base import VectorStore


class FakeLLMProvider(LLMProvider):
    def __init__(
        self,
        tokens: list[str] | None = None,
        plan_response: str = (
            '{"tool": "search_knowledge_base", "arguments": {"query": "question", "top_k": 4}}'
        ),
    ):
        self._tokens = tokens or ["The", " system", " works."]
        self.plan_response = plan_response

    async def generate(
        self, prompt: str, *, system: str | None = None, json_mode: bool = False
    ) -> str:
        if json_mode:
            return self.plan_response
        return "".join(self._tokens)

    async def stream(self, prompt: str, *, system: str | None = None):
        for token in self._tokens:
            yield token

    def check(self) -> bool:
        return True


class FakeEmbeddingProvider(EmbeddingProvider):
    def __init__(self, dimension: int = 8, vector: list[float] | None = None):
        self.dimension = dimension
        self._vector = vector or [0.1] * dimension
        self.embedded_texts: list[str] = []
        self.embedded_queries: list[str] = []

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.embedded_texts.extend(texts)
        return [self._vector[:] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        self.embedded_queries.append(text)
        return self._vector[:]

    def check(self) -> bool:
        return True


class FakeVectorStore(VectorStore):
    def __init__(self):
        self.chunks: list[tuple[str, list]] = []
        self.chunked: list[dict] = []
        self.deleted: list[tuple[str, str]] = []
        self.query_results: list[dict] = []

    def add_chunks(
        self, knowledge_base_id: str, chunks: list, embeddings: list[list[float]]
    ) -> None:
        for chunk in chunks:
            self.chunks.append((knowledge_base_id, chunk))
            self.chunked.append(
                {
                    "chunk_id": chunk.chunk_id,
                    "text": chunk.text,
                    "document_id": chunk.document_id,
                    "document_name": chunk.document_name,
                    "page": chunk.page,
                    "section": chunk.section,
                    "score": 1.0,
                }
            )

    def query(
        self,
        knowledge_base_id: str,
        embedding: list[float],
        top_k: int,
        min_score: float | None = None,
        where: dict = None,
    ) -> list[dict]:
        if where:
            return [
                item
                for item in self.query_results
                if item.get("document_id") == where.get("document_id")
            ]
        return self.query_results

    def get_document_chunks(
        self, knowledge_base_id: str, document_id: str, limit: int = 12
    ) -> list[dict]:
        return [
            item
            for item in self.chunked
            if item.get("document_id") == document_id
        ][:limit]

    def delete_document(self, knowledge_base_id: str, document_id: str) -> None:
        self.deleted.append((knowledge_base_id, document_id))

    def document_chunk_count(self, knowledge_base_id: str, document_id: str) -> int:
        return sum(
            1
            for kb, chunk in self.chunks
            if kb == knowledge_base_id and chunk.document_id == document_id
        )


def make_pdf(text: str) -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), text, fontsize=12, fontname="helv")
    data = document.tobytes()
    document.close()
    return data