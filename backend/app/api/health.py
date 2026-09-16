from fastapi import APIRouter, Depends

from app.embeddings.base import EmbeddingProvider
from app.models.schemas import HealthOut

from .deps import get_embedding_provider, get_llm_provider

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthOut)
def health(
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
) -> HealthOut:
    llm_provider = get_llm_provider()
    llm_ok = llm_provider.check()
    embedding_ok = embedding_provider.check()
    return HealthOut(
        status="ok" if llm_ok and embedding_ok else "degraded",
        llm_available=llm_ok,
        embedding_available=embedding_ok,
    )