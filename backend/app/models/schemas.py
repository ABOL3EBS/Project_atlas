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
    conversation_id: str | None = None


class ConversationOut(BaseModel):
    id: str
    knowledge_base_id: str
    created_at: str


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    created_at: str


class ConversationDetailOut(ConversationOut):
    messages: list[MessageOut]


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


class TraceEventOut(BaseModel):
    event_id: str
    trace_id: str
    event_type: str
    status: str
    timestamp: str
    conversation_id: str | None = None
    knowledge_base_id: str
    latency_ms: float | None = None
    metadata: dict = Field(default_factory=dict)
    error: dict | None = None


class TraceOut(BaseModel):
    trace_id: str
    conversation_id: str | None = None
    knowledge_base_id: str
    question: str | None = None
    status: str
    started_at: str
    completed_at: str | None = None
    latency_ms: float | None = None
    events: list[TraceEventOut] = Field(default_factory=list)


class TraceListOut(BaseModel):
    conversation_id: str
    knowledge_base_id: str
    traces: list[TraceOut] = Field(default_factory=list)