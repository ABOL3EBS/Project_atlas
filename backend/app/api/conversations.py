from fastapi import APIRouter, Depends, HTTPException, status

from app.memory.conversation_store import ConversationStore
from app.models.schemas import ConversationDetailOut, ConversationOut, MessageOut

from .deps import get_conversation_store

router = APIRouter(tags=["conversations"])


@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(
    knowledge_base_id: str = "default",
    conversation_store: ConversationStore = Depends(get_conversation_store),
) -> list[ConversationOut]:
    return [
        ConversationOut(
            id=conversation["id"],
            knowledge_base_id=conversation["knowledge_base_id"],
            created_at=conversation["created_at"],
        )
        for conversation in conversation_store.list_conversations(knowledge_base_id)
    ]


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailOut)
def get_conversation(
    conversation_id: str,
    knowledge_base_id: str = "default",
    conversation_store: ConversationStore = Depends(get_conversation_store),
) -> ConversationDetailOut:
    conversation = conversation_store.get_conversation(
        knowledge_base_id, conversation_id
    )
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found"
        )
    messages = conversation_store.list_messages(conversation_id)
    return ConversationDetailOut(
        id=conversation["id"],
        knowledge_base_id=conversation["knowledge_base_id"],
        created_at=conversation["created_at"],
        messages=[MessageOut(**message) for message in messages],
    )