"""Retrieval experiment pipelines.

Each pipeline is a measurement target for M4. The interfaces keep the stages
swappable: `Reranker` is where a cross-encoder would later plug in, and
`QueryTransformer` is a pure function of the query except for the LLM variants.

All pipelines return the same shape so the evaluation harness treats them
identically: ranked chunks and a per-phase timing breakdown.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.llm.base import LLMProvider

from .retriever import RetrievedChunk

DEFAULT_CANDIDATE_POOL = 25
DEFAULT_VARIANTS = 3


@dataclass
class PipelineResult:
    results: list[RetrievedChunk]
    timings: dict[str, float] = field(default_factory=dict)


def now_ms() -> float:
    return time.perf_counter() * 1000.0


class Reranker(ABC):
    @abstractmethod
    def rerank(
        self, query: str, candidates: list[RetrievedChunk], top_k: int
    ) -> list[RetrievedChunk]:
        raise NotImplementedError


class BM25Reranker(Reranker):
    def __init__(self, corpus: list[str]):
        from .bm25 import BM25Index

        self._index = BM25Index(corpus)

    def rerank(
        self, query: str, candidates: list[RetrievedChunk], top_k: int
    ) -> list[RetrievedChunk]:
        return self._index.rerank(query, candidates, top_k)


class QueryTransformer(ABC):
    @abstractmethod
    async def transform(self, query: str) -> list[str]:
        raise NotImplementedError


class IdentityQueryTransformer(QueryTransformer):
    async def transform(self, query: str) -> list[str]:
        return [query]


class LLMQueryRewriter(QueryTransformer):
    _SYSTEM = (
        "You are improving a search query for a vector database. Rewrite the user's "
        "question into a single concise standalone search query that captures the key "
        "terms and synonyms. Reply with exactly one line and no explanation."
    )

    def __init__(self, llm_provider: LLMProvider):
        self._llm = llm_provider

    async def transform(self, query: str) -> list[str]:
        try:
            rewritten = (await self._llm.generate(query, system=self._SYSTEM)).strip()
        except Exception:
            return [query]
        return [rewritten] if rewritten else [query]


class LLMMultiQueryTransformer(QueryTransformer):
    _SYSTEM = (
        "Create up to {count} distinct search queries for the user's question. Cover "
        "different phrasings, synonyms, and narrower aspects. Return one query per "
        "line, with no numbering and no explanation."
    )

    def __init__(self, llm_provider: LLMProvider, variants: int = DEFAULT_VARIANTS):
        self._llm = llm_provider
        self._variants = variants

    async def transform(self, query: str) -> list[str]:
        queries = [query]
        try:
            raw = await self._llm.generate(
                query, system=self._SYSTEM.format(count=self._variants)
            )
        except Exception:
            return queries
        for line in raw.splitlines():
            line = line.strip().strip("-*")
            if line and line not in queries:
                queries.append(line)
            if len(queries) >= self._variants:
                break
        return queries


def baseline_search(retriever, knowledge_base_id: str, query: str, top_k: int) -> PipelineResult:
    timings: dict[str, float] = {}
    _begin = now_ms()
    results = retriever.search(knowledge_base_id, query, top_k=top_k)
    timings["search"] = now_ms() - _begin
    return PipelineResult(results=results, timings=timings)


async def rewrite_search(
    retriever, transformer: QueryTransformer, knowledge_base_id: str, query: str, top_k: int
) -> PipelineResult:
    timings: dict[str, float] = {}
    _begin = now_ms()
    queries = await transformer.transform(query)
    timings["rewrite"] = now_ms() - _begin
    _begin = now_ms()
    results = retriever.search(knowledge_base_id, queries[0], top_k=top_k)
    timings["search"] = now_ms() - _begin
    return PipelineResult(results=results, timings=timings)


def reranked_search(
    retriever,
    reranker: Reranker,
    knowledge_base_id: str,
    query: str,
    top_k: int,
    candidate_pool: int = DEFAULT_CANDIDATE_POOL,
) -> PipelineResult:
    timings: dict[str, float] = {}
    _begin = now_ms()
    candidates = retriever.search(knowledge_base_id, query, top_k=candidate_pool)
    timings["search"] = now_ms() - _begin
    _begin = now_ms()
    results = reranker.rerank(query, candidates, top_k)
    timings["rerank"] = now_ms() - _begin
    return PipelineResult(results=results, timings=timings)


async def multi_query_search(
    retriever,
    transformer: QueryTransformer,
    reranker: Reranker,
    knowledge_base_id: str,
    query: str,
    top_k: int,
    candidate_pool: int = DEFAULT_CANDIDATE_POOL,
) -> PipelineResult:
    timings: dict[str, float] = {}
    _begin = now_ms()
    queries = await transformer.transform(query)
    timings["rewrite"] = now_ms() - _begin

    _begin = now_ms()
    merged: dict[str, RetrievedChunk] = {}
    for variant in queries:
        for chunk in retriever.search(knowledge_base_id, variant, top_k=candidate_pool):
            existing = merged.get(chunk.chunk_id)
            if existing is None or chunk.score > existing.score:
                merged[chunk.chunk_id] = chunk
    timings["search"] = now_ms() - _begin

    _begin = now_ms()
    results = reranker.rerank(query, list(merged.values()), top_k)
    timings["rerank"] = now_ms() - _begin
    return PipelineResult(results=results, timings=timings)