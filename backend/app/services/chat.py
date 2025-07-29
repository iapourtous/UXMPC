from typing import List, Dict, Optional
from app.models.llm import LLMProfile
from app.services.llm_crud import LLMProfileCRUD
from app.core.llm_client import llm_client
import logging

logger = logging.getLogger(__name__)


class ChatService:
    @staticmethod
    async def send_message(
        llm_profile_id: str,
        message: str,
        conversation_history: List[Dict[str, str]] = None
    ) -> Dict[str, any]:
        """Send a message to an LLM using the specified profile"""
        
        # Get the LLM profile
        llm_crud = LLMProfileCRUD()
        profile = await llm_crud.get(llm_profile_id)
        if not profile:
            raise ValueError(f"LLM profile {llm_profile_id} not found")
        
        if not profile.active:
            raise ValueError(f"LLM profile {profile.name} is not active")
        
        # Use centralized LLM client with conversation history support
        return await llm_client.call_with_history(
            llm_profile=profile,
            message=message,
            conversation_history=conversation_history,
            temperature=profile.temperature,
            max_tokens=profile.max_tokens
        )