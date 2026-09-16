"""Pure retrieval metric computations. No I/O, fully unit-testable.

Score units: a "document" is a document name; ranking lists must be document names
in retrieval order (deduplicated by the caller when document-level recall is wanted).
"""

from __future__ import annotations


def recall_at_k(ranked_documents: list[str], expected: list[str], k: int) -> float:
    if not expected:
        return 1.0
    top_k = set(ranked_documents[:k])
    hits = len(top_k & set(expected))
    return hits / len(expected)


def mrr(ranked_documents: list[str], expected: list[str]) -> float:
    expected_set = set(expected)
    for rank, document in enumerate(ranked_documents, start=1):
        if document in expected_set:
            return 1.0 / rank
    return 0.0


def recall_at_documents(ranked_documents: list[str], expected: list[str], k: int) -> float:
    """Recall@K over unique expected documents, deduplicating the ranking first."""
    return recall_at_k(_deduplicate(ranked_documents), expected, k)


def mrr_documents(ranked_documents: list[str], expected: list[str]) -> float:
    return mrr(_deduplicate(ranked_documents), expected)


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = (len(ordered) - 1) * percentile / 100.0
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def _deduplicate(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result