from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.config import Settings, get_settings
from app.models.schemas import ChatRequest
from app.services.chat_service import ChatService

from .deps import get_chat_service
from .sse import embed_event

router = APIRouter(tags=["chat"])


@router.post("/chat")
async def chat(
    request: ChatRequest,
    chat_service: ChatService = Depends(get_chat_service),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    knowledge_base_id = request.knowledge_base_id or settings.default_knowledge_base_id

    async def event_stream():
        async for event in chat_service.run(knowledge_base_id, request.message):
            yield embed_event(event)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )