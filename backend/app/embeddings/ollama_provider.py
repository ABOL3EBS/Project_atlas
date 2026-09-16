import httpx

from .base import EmbeddingProvider


def _ollama_reachable(base_url: str) -> bool:
    try:
        response = httpx.get(f"{base_url}/api/tags", timeout=5)
        return response.is_success
    except httpx.HTTPError:
        return False


class OllamaEmbeddingProvider(EmbeddingProvider):
    def __init__(self, base_url: str, model: str):
        self._base_url = base_url.rstrip("/")
        self._model = model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    def _embed(self, text: str) -> list[float]:
        response = httpx.post(
            f"{self._base_url}/api/embed",
            json={"model": self._model, "input": text},
            timeout=120,
        )
        response.raise_for_status()
        data = response.json()
        return data["embeddings"][0]

    def check(self) -> bool:
        return _ollama_reachable(self._base_url)