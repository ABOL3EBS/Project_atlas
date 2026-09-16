"""Minimal BM25 scoring for lexical reranking.

Implemented on the standard library so the experiment pipeline stays dependency-free.
A cross-encoder reranker can be slotted in later behind the same interface.
"""

from __future__ import annotations

import math
import re
from collections import Counter

from .retriever import RetrievedChunk

_TOKEN_RE = re.compile(r"[a-z0-9]+")

_K1 = 1.5
_B = 0.75


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _term_frequency(terms: list[str]) -> Counter:
    return Counter(terms)


class BM25Index:
    """Precomputed document frequencies and length statistics over a corpus."""

    def __init__(self, corpus: list[str]):
        self._document_frequencies: Counter = Counter()
        self._documents = corpus
        lengths = []
        for document in corpus:
            terms = set(tokenize(document))
            for term in terms:
                self._document_frequencies[term] += 1
            lengths.append(len(tokenize(document)))
        self._average_length = (sum(lengths) / len(lengths)) if lengths else 1.0
        self._total = len(corpus)

    def _idf(self, term: str) -> float:
        frequency = self._document_frequencies.get(term, 0)
        return math.log(1.0 + (self._total - frequency + 0.5) / (frequency + 0.5))

    def score(self, query: str, document: str) -> float:
        if not query or not document:
            return 0.0
        query_terms = set(tokenize(query))
        doc_terms = tokenize(document)
        document_length = len(doc_terms) or 1
        frequencies = _term_frequency(doc_terms)
        score = 0.0
        for term in query_terms:
            frequency = frequencies.get(term, 0)
            if frequency == 0:
                continue
            numerator = frequency * (_K1 + 1.0)
            denominator = frequency + _K1 * (
                1.0 - _B + _B * document_length / self._average_length
            )
            score += self._idf(term) * numerator / denominator
        return score

    def rerank(
        self, query: str, candidates: list[RetrievedChunk], top_k: int | None = None
    ) -> list[RetrievedChunk]:
        scored = sorted(
            candidates, key=lambda chunk: self.score(query, chunk.text), reverse=True
        )
        return scored[:top_k] if top_k is not None else scored