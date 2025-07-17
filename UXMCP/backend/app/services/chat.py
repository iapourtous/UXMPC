import httpx
from typing import List, Dict, Optional
from app.models.llm import LLMProfile
from app.services.llm_crud import LLMProfileCRUD
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
        
        # Prepare the messages
        messages = []
        
        # Add system prompt if provided
        if profile.system_prompt:
            messages.append({"role": "system", "content": profile.system_prompt})
        
        # Add conversation history
        if conversation_history:
            messages.extend(conversation_history)
            
        # Add the new user message
        messages.append({"role": "user", "content": message})
        
        # Determine the API endpoint
        endpoint = profile.endpoint or "https://api.openai.com/v1/chat/completions"
        
        # Prepare the request
        headers = {
            "Authorization": f"Bearer {profile.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": profile.model,
            "messages": messages,
            "temperature": profile.temperature,
            "max_tokens": profile.max_tokens
        }
        
        # Add response_format if mode is json
        if profile.mode == "json":
            payload["response_format"] = {"type": "json_object"}
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    endpoint,
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                
                result = response.json()
                
                # Extract the assistant's message
                assistant_message = result["choices"][0]["message"]["content"]
                
                return {
                    "success": True,
                    "message": assistant_message,
                    "usage": result.get("usage", {}),
                    "model": result.get("model", profile.model)
                }
                
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error when calling LLM API: {e}")
            error_detail = e.response.text if e.response else str(e)
            return {
                "success": False,
                "error": f"API Error: {e.response.status_code}",
                "detail": error_detail
            }
        except Exception as e:
            logger.error(f"Error calling LLM API: {e}")
            return {
                "success": False,
                "error": str(e)
            }