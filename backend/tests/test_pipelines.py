from conftest import FakeEmbeddingProvider, FakeLLMProvider, FakeVectorStore

from app.retrieval.pipelines import (
    BM25Reranker,
    IdentityQueryTransformer,
    LLMMultiQueryTransformer,
    LLMQueryRewriter,
    baseline_search,
    multi_query_search,
    reranked_search,
    rewrite_search,
)
from app.retrieval.retriever import Retriever

BATTERIES = "lithium iron phosphate batteries have excellent thermal stability for storage"
CRYPTO = "nickel manganese cobalt cells store more energy per kilogram"
NGINX = "nginx proxy servers handle worker connections over the network"
SOLAR = "solar monocrystalline panels reach twenty two percent efficiency"

CORPUS = [BATTERIES, CRYPTO, NGINX, SOLAR]


def _results(*pairs: tuple[str, str]) -> list[dict]:
    return [
        {
            "chunk_id": f"{name}-0",
            "text": text,
            "document_id": name,
            "document_name": name,
            "page": None,
            "section": None,
            "score": 0.9 - index * 0.01,
        }
        for index, (name, text) in enumerate(pairs)
    ]


class ScriptedVectorStore(FakeVectorStore):
    def __init__(self, embedding_provider: FakeEmbeddingProvider, responses: dict[str, list[dict]]):
        super().__init__()
        self._embedding_provider = embedding_provider
        self._responses = responses

    def query(self, knowledge_base_id, embedding, top_k, min_score=None, where=None):
        query = self._embedding_provider.embedded_queries[-1]
        items = [
            item
            for item in self._responses.get(query, [])
            if min_score is None or item["score"] >= min_score
        ]
        return items[:top_k]


def _retriever(provider: FakeEmbeddingProvider, store: FakeVectorStore) -> Retriever:
    return Retriever(store, provider, top_k=5, min_score=0.20)


def test_baseline_search_runs_single_search_and_records_timing():
    provider = FakeEmbeddingProvider(vector=[0.1] * 8)
    store = ScriptedVectorStore(provider, {"question": _results(("solar.md", SOLAR))})
    retriever = _retriever(provider, store)
    result = baseline_search(retriever, "kb", "question", top_k=5)
    assert [chunk.document_name for chunk in result.results] == ["solar.md"]
    assert "search" in result.timings


def test_rewrite_search_uses_the_rewritten_query():
    provider = FakeEmbeddingProvider(vector=[0.1] * 8)
    store = ScriptedVectorStore(
        provider, {"The system works.": _results(("batteries.md", BATTERIES))}
    )
    retriever = _retriever(provider, store)
    transformer = LLMQueryRewriter(FakeLLMProvider())
    result = asyncio_run(rewrite_search(retriever, transformer, "kb", "original question", top_k=5))
    assert result.results
    assert provider.embedded_queries == ["The system works."]


def test_rewrite_falls_back_to_original_query_on_llm_failure():
    class BrokenLLM(FakeLLMProvider):
        async def generate(self, prompt, *, system=None, json_mode=False):
            raise ConnectionError("ollama down")

    provider = FakeEmbeddingProvider(vector=[0.1] * 8)
    store = ScriptedVectorStore(
        provider, {"original question": _results(("solar.md", SOLAR))}
    )
    retriever = _retriever(provider, store)
    transformer = LLMQueryRewriter(BrokenLLM())
    result = asyncio_run(rewrite_search(retriever, transformer, "kb", "original question", top_k=5))
    assert provider.embedded_queries == ["original question"]
    assert result.results


def test_multi_query_deduplicates_across_variants_and_reranks():
    provider = FakeEmbeddingProvider(vector=[0.1] * 8)
    store = ScriptedVectorStore(
        provider,
        {
            "original question": _results(("batteries.md", BATTERIES), ("crypto.md", CRYPTO)),
            "The system works.": _results(("crypto.md", CRYPTO), ("nginx.md", NGINX)),
        },
    )
    retriever = _retriever(provider, store)
    transformer = LLMMultiQueryTransformer(FakeLLMProvider(), variants=3)
    reranker = BM25Reranker(CORPUS)
    result = asyncio_run(
        multi_query_search(retriever, transformer, reranker, "kb", "original question", top_k=5)
    )
    assert provider.embedded_queries == ["original question", "The system works."]
    assert {chunk.chunk_id for chunk in result.results} == {
        "batteries.md-0",
        "crypto.md-0",
        "nginx.md-0",
    }
    assert len(result.results) == 3


def test_multi_query_falls_back_to_single_query_when_llm_unavailable():
    class BrokenLLM(FakeLLMProvider):
        async def generate(self, prompt, *, system=None, json_mode=False):
            raise ConnectionError("ollama down")

    provider = FakeEmbeddingProvider(vector=[0.1] * 8)
    store = ScriptedVectorStore(
        provider,
        {"only query": _results(("batteries.md", BATTERIES), ("nginx.md", NGINX))},
    )
    retriever = _retriever(provider, store)
    transformer = LLMMultiQueryTransformer(BrokenLLM(), variants=3)
    reranker = BM25Reranker(CORPUS)
    result = asyncio_run(
        multi_query_search(retriever, transformer, reranker, "kb", "only query", top_k=5)
    )
    assert provider.embedded_queries == ["only query"]
    assert len(result.results) == 2


def test_reranked_search_uses_candidate_pool_then_trims_to_top_k():
    provider = FakeEmbeddingProvider(vector=[0.1] * 8)
    store = ScriptedVectorStore(
        provider,
        {"question": _results(("solar.md", SOLAR), ("nginx.md", NGINX))},
    )
    retriever = _retriever(provider, store)
    reranker = BM25Reranker(CORPUS)
    result = reranked_search(retriever, reranker, "kb", "question", top_k=1, candidate_pool=2)
    assert len(result.results) == 1
    assert "search" in result.timings and "rerank" in result.timings


async def test_identity_transformer_returns_single_query():
    transformer = IdentityQueryTransformer()
    assert await transformer.transform("q") == ["q"]
    assert await transformer.transform("") == [""]


def asyncio_run(coro):
    import asyncio

    return asyncio.run(coro)