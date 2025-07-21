"""
Meta Chat API

Simple endpoint for the meta-chat system
"""

from fastapi import APIRouter, HTTPException
import logging

from app.models.meta_chat import MetaChatRequest, MetaChatResponse
from app.services.meta_chat_service import create_meta_chat

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/query", response_model=MetaChatResponse)
async def query_meta_chat(request: MetaChatRequest):
    """
    Process a user query through the meta-chat system
    
    This endpoint:
    1. Analyzes the user's request
    2. Determines if it can answer directly or needs an agent
    3. Finds or creates an appropriate agent if needed
    4. Returns the response
    """
    try:
        logger.info(f"Meta-chat query: {request.message[:100]}...")
        
        # Create meta chat service
        meta_chat = await create_meta_chat(request.llm_profile)
        
        # Process the request
        response = await meta_chat.process_request(request)
        
        logger.info(f"Meta-chat response: success={response.success}, agent={response.agent_used}")
        
        return response
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Meta-chat error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")