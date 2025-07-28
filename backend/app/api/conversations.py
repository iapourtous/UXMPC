from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from app.models.conversation import (
    ConversationCreate, ConversationUpdate, Conversation,
    ConversationList, ConversationSummary, MessageCreate
)
from app.services.conversation_crud import conversation_crud
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/", response_model=Conversation)
async def create_conversation(conversation: ConversationCreate):
    """Create a new conversation"""
    try:
        return await conversation_crud.create(conversation)
    except Exception as e:
        logger.error(f"Failed to create conversation: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create conversation")


@router.get("/", response_model=ConversationList)
async def list_conversations(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    active_only: bool = Query(False),
    user_id: Optional[str] = Query(None)
):
    """List conversations with pagination"""
    try:
        return await conversation_crud.list(
            skip=skip,
            limit=limit,
            active_only=active_only,
            user_id=user_id
        )
    except Exception as e:
        logger.error(f"Failed to list conversations: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list conversations")


@router.get("/summaries", response_model=List[ConversationSummary])
async def get_conversation_summaries(
    user_id: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=50)
):
    """Get conversation summaries for quick display"""
    try:
        return await conversation_crud.get_summaries(
            user_id=user_id,
            limit=limit
        )
    except Exception as e:
        logger.error(f"Failed to get conversation summaries: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get conversation summaries")


@router.get("/{conversation_id}", response_model=Conversation)
async def get_conversation(conversation_id: str):
    """Get a specific conversation"""
    conversation = await conversation_crud.get(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@router.put("/{conversation_id}", response_model=Conversation)
async def update_conversation(conversation_id: str, update: ConversationUpdate):
    """Update a conversation"""
    conversation = await conversation_crud.update(conversation_id, update)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@router.delete("/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a conversation"""
    success = await conversation_crud.delete(conversation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"message": "Conversation deleted successfully"}


@router.post("/{conversation_id}/messages", response_model=Conversation)
async def add_message_to_conversation(conversation_id: str, message: MessageCreate):
    """Add a message to a conversation"""
    conversation = await conversation_crud.add_message(conversation_id, message)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@router.post("/{conversation_id}/clear")
async def clear_conversation_messages(conversation_id: str):
    """Clear all messages from a conversation"""
    success = await conversation_crud.clear_messages(conversation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"message": "Messages cleared successfully"}


@router.get("/latest", response_model=Optional[Conversation])
async def get_latest_conversation(
    user_id: Optional[str] = Query(None)
):
    """Get the most recent conversation"""
    try:
        conversation = await conversation_crud.get_latest_conversation(
            user_id=user_id
        )
        if not conversation:
            raise HTTPException(status_code=404, detail="No conversation found")
        return conversation
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get latest conversation: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get latest conversation")