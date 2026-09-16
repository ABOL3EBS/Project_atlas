import math

from app.embeddings.base import EmbeddingProvider

DEFAULT_WINDOW = 24
DEFAULT_MAX_RESULTS = 3


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    norm_left = math.sqrt(sum(a * a for a in left))
    norm_right = math.sqrt(sum(b * b for b in right))
    if norm_left == 0.0 or norm_right == 0.0:
        return 0.0
    return dot / (norm_left * norm_right)


class MemorySelector:
    """Selectively picks prior messages relevant to a follow-up question.

    Only the last ``window`` messages are candidates, and at most
    ``max_results`` are returned — never the full conversation. The
    immediately-preceding user message (when within the window) is kept as a
    recency anchor so unresolvable pronouns like "it" still have context.
    """

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        max_results: int = DEFAULT_MAX_RESULTS,
        window: int = DEFAULT_WINDOW,
    ):
        self._embedding_provider = embedding_provider
        self._max_results = max_results
        self._window = window

    def select(
        self,
        messages: list[dict],
        question: str,
    ) -> list[dict]:
        candidates = messages[-self._window :]
        if not candidates:
            return []
        query_vector = self._embedding_provider.embed_query(question)

        scored = []
        for index, message in enumerate(candidates):
            vector = self._embedding_provider.embed_documents([message["content"]])[0]
            scored.append(
                (index, _cosine_similarity(query_vector, vector), message)
            )
        scored.sort(key=lambda item: (-item[1], -item[0]))

        selected = scored[: self._max_results]

        recent = candidates[-1]
        if recent not in [item[2] for item in selected]:
            selected = selected[: self._max_results - 1]
            selected.append((len(candidates) - 1, 0.0, recent))

        selected.sort(key=lambda item: item[0])
        return [message for _, _, message in selected if message["content"].strip()]