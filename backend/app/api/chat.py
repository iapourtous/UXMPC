from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
from app.services.chat import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    llm_profile_id: str
    message: str
    conversation_history: Optional[List[Dict[str, str]]] = None


class ChatResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    error: Optional[str] = None
    detail: Optional[str] = None
    usage: Optional[Dict] = None
    model: Optional[str] = None


@router.post("/", response_model=ChatResponse)
async def send_message(request: ChatRequest):
    """Send a message to the selected LLM"""
    try:
        result = await ChatService.send_message(
            llm_profile_id=request.llm_profile_id,
            message=request.message,
            conversation_history=request.conversation_history
        )
        return ChatResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")