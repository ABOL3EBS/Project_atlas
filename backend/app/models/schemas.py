from pydantic import BaseModel, Field


class DocumentOut(BaseModel):
    id: str
    knowledge_base_id: str
    name: str
    size: int
    status: str
    chunk_count: int = 0
    error: str | None = None
    created_at: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4096)
    knowledge_base_id: str = "default"


class ChatChunkBrief(BaseModel):
    document_id: str
    document_name: str
    page: int | None = None
    section: str | None = None
    score: float


class HealthOut(BaseModel):
    status: str
    llm_available: bool
    embedding_available: bool