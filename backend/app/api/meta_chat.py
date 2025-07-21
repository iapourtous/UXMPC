"""
Meta Chat API

Simple endpoint for the meta-chat system
"""

from fastapi import APIRouter, HTTPException
import logging

from app.models.meta_chat import (
    MetaChatRequest, MetaChatResponse, ClarificationQuestionnaire, 
    ClarificationAnswers
)
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


@router.post("/clarify", response_model=ClarificationQuestionnaire)
async def generate_clarification_questionnaire(request: dict):
    """
    Generate clarification questions for a user query
    
    This endpoint:
    1. Analyzes the user's query to determine its type
    2. Generates contextual clarification questions
    3. Returns a questionnaire with session ID for tracking
    """
    try:
        query = request.get("message")
        llm_profile = request.get("llm_profile")
        
        if not query or not llm_profile:
            raise HTTPException(status_code=400, detail="Message and llm_profile are required")
        
        logger.info(f"Generating clarification questions for: {query[:100]}...")
        
        # Create meta chat service
        meta_chat = await create_meta_chat(llm_profile)
        
        # Generate questionnaire
        questionnaire = await meta_chat.generate_clarification_questionnaire(query, llm_profile)
        
        logger.info(f"Generated {len(questionnaire.questions)} questions for session {questionnaire.session_id}")
        
        return questionnaire
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Clarification generation error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.post("/process-clarifications", response_model=MetaChatResponse)
async def process_clarifications(request: ClarificationAnswers):
    """
    Process a query with clarification answers
    
    This endpoint:
    1. Retrieves the session and clarification questions
    2. Processes answers to create enhanced message and auto-generated instructions
    3. Executes the enhanced query through the normal meta-chat flow
    """
    try:
        logger.info(f"Processing clarifications for session: {request.session_id}")
        
        # Get session LLM profile from stored session data
        from app.services.meta_chat_service import SESSIONS
        session = SESSIONS.get(request.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found or expired")
        
        # Create meta chat service
        meta_chat = await create_meta_chat(session.llm_profile)
        
        # Process with clarifications
        response = await meta_chat.process_with_clarifications(request.session_id, request.answers)
        
        logger.info(f"Clarification processing: success={response.success}, agent={response.agent_used}")
        
        return response
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Clarification processing error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")