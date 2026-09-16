import json

from app.embeddings.base import EmbeddingProvider
from app.llm.base import LLMProvider


def embed_event(payload: dict) -> str:
    return f"event: {payload['type']}\ndata: {json.dumps(_without_type(payload))}\n\n"


def _without_type(payload: dict) -> dict:
    return {key: value for key, value in payload.items() if key != "type"}


def check_provider_availability(
    embedding_provider: EmbeddingProvider, llm_provider: LLMProvider
) -> tuple[bool, bool]:
    embedding_ok = _try_embedding(embedding_provider)
    llm_ok = _try_llm(llm_provider)
    return llm_ok, embedding_ok


def _try_embedding(provider: EmbeddingProvider) -> bool:
    try:
        provider.embed_query("ping")
        return True
    except Exception:
        return False


def _try_llm(provider: LLMProvider) -> bool:
    return True