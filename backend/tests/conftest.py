import pymupdf

from app.embeddings.base import EmbeddingProvider
from app.llm.base import LLMProvider
from app.retrieval.base import VectorStore


class FakeLLMProvider(LLMProvider):
    def __init__(self, tokens: list[str] | None = None):
        self._tokens = tokens or ["The", " system", " works."]

    async def generate(self, prompt: str, *, system: str | None = None) -> str:
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
        self.deleted: list[tuple[str, str]] = []
        self.query_results: list[dict] = []

    def add_chunks(
        self, knowledge_base_id: str, chunks: list, embeddings: list[list[float]]
    ) -> None:
        for chunk in chunks:
            self.chunks.append((knowledge_base_id, chunk))

    def query(
        self,
        knowledge_base_id: str,
        embedding: list[float],
        top_k: int,
        min_score: float | None = None,
    ) -> list[dict]:
        return self.query_results

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