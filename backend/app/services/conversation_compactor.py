"""
Conversation Compactor Service

Handles intelligent compaction of long conversations to optimize token usage
while preserving context and recent messages.
"""

from typing import List, Dict, Any, Optional, Tuple
import logging
from datetime import datetime
import httpx
import json

from app.models.settings import GlobalSettings
from app.services.settings_crud import settings_crud
from app.services.llm_crud import llm_crud

logger = logging.getLogger(__name__)


class ConversationCompactor:
    """Service for compacting conversations to reduce token usage"""
    
    async def should_compact(
        self, 
        messages: List[Dict[str, Any]], 
        settings: Optional[GlobalSettings] = None
    ) -> bool:
        """
        Determine if conversation should be compacted based on settings
        
        Args:
            messages: List of conversation messages
            settings: Global settings (will fetch if not provided)
            
        Returns:
            True if compaction should occur
        """
        if not settings:
            settings = await settings_crud.get_or_create()
        
        # Check if compaction is enabled
        if not settings.compaction_settings.enabled:
            return False
        
        # Check if we have enough messages to compact
        if len(messages) <= settings.compaction_settings.message_threshold:
            return False
        
        # Check if we have a summary LLM profile configured
        if not settings.summary_llm_profile:
            logger.warning("Compaction enabled but no summary LLM profile configured")
            return False
        
        return True
    
    async def compact_conversation(
        self, 
        messages: List[Dict[str, Any]], 
        user_context: Optional[str] = None,
        settings: Optional[GlobalSettings] = None,
        current_user_message: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], bool]:
        """
        Compact a conversation by summarizing old messages
        
        Args:
            messages: Full conversation history
            user_context: User context to prepend
            settings: Global settings (will fetch if not provided)
            current_user_message: Current user message to optimize summary for
            
        Returns:
            Tuple of (compacted messages for agent, whether compaction occurred)
        """
        if not settings:
            settings = await settings_crud.get_or_create()
        
        # Check if we should compact
        if not await self.should_compact(messages, settings):
            # No compaction, just add user context if provided
            if user_context:
                return self._add_user_context(messages, user_context), False
            return messages, False
        
        try:
            # Get the summary LLM profile
            llm_profile = await llm_crud.get_by_name(settings.summary_llm_profile)
            if not llm_profile or not llm_profile.active:
                logger.error(f"Summary LLM profile '{settings.summary_llm_profile}' not found or inactive")
                return messages, False
            
            # Calculate split point
            preserve_count = settings.compaction_settings.preserve_last_n
            messages_to_summarize = messages[:-preserve_count]
            messages_to_preserve = messages[-preserve_count:]
            
            # Create summary of old messages
            summary = await self._create_summary(
                messages_to_summarize, 
                llm_profile,
                settings.compaction_settings.summary_max_tokens,
                current_user_message
            )
            
            # Build compacted conversation
            compacted_messages = []
            
            # Add user context FIRST if provided and not already in preserved messages
            # Check if User Context is already in the messages to avoid duplication
            has_user_context = any(
                msg.get("role") == "system" and "User Context:" in msg.get("content", "")
                for msg in messages_to_preserve
            )
            
            if user_context and not has_user_context:
                compacted_messages.append({
                    "role": "system",
                    "content": f"User Context: {user_context}"
                })
            
            # Add summary as a system message
            compacted_messages.append({
                "role": "system",
                "content": f"Previous Conversation Summary: {summary}"
            })
            
            # Add preserved recent messages
            compacted_messages.extend(messages_to_preserve)
            
            logger.info(
                f"Compacted conversation: {len(messages)} messages -> "
                f"{len(compacted_messages)} messages (summarized {len(messages_to_summarize)})"
            )
            
            return compacted_messages, True
            
        except Exception as e:
            logger.error(f"Failed to compact conversation: {str(e)}")
            # On error, return original messages with user context
            if user_context:
                return self._add_user_context(messages, user_context), False
            return messages, False
    
    async def _create_summary(
        self, 
        messages: List[Dict[str, Any]], 
        llm_profile: Any,
        max_tokens: int,
        current_user_message: Optional[str] = None
    ) -> str:
        """Create a concise summary of messages using LLM"""
        
        # Format messages for summarization
        conversation_text = "\n".join([
            f"{msg['role'].upper()}: {msg['content']}"
            for msg in messages
        ])
        
        # Create context-aware summarization prompt
        context_instruction = ""
        if current_user_message:
            context_instruction = f"""
Current user query: "{current_user_message}"

Pay special attention to information that might be relevant to answering this current query. """

        prompt = f"""Summarize the following conversation in {max_tokens} tokens or less. 
Focus on key points, decisions made, and important context.{context_instruction}

Conversation:
{conversation_text}

Summary:"""
        
        try:
            # Prepare the request to LLM
            messages_for_llm = []
            
            # Add system prompt if provided in profile
            if hasattr(llm_profile, 'system_prompt') and llm_profile.system_prompt:
                messages_for_llm.append({"role": "system", "content": llm_profile.system_prompt})
            
            # Add the summarization request
            messages_for_llm.append({"role": "user", "content": prompt})
            
            # Determine the API endpoint and provider (same pattern as agent_executor.py)
            endpoint = llm_profile.endpoint or "https://api.openai.com/v1/chat/completions"
            
            # Use standard OpenAI-compatible format (works for OpenAI, Groq, and other compatible APIs)
            headers = {
                "Authorization": f"Bearer {llm_profile.api_key}",
                "Content-Type": "application/json"
            }
            
            body = {
                "model": llm_profile.model,
                "messages": messages_for_llm,
                "max_tokens": max_tokens,
                "temperature": 0.7  # Lower temperature for more focused summaries
            }
            
            # Make the request
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    endpoint,
                    headers=headers,
                    json=body,
                    timeout=30.0
                )
                response.raise_for_status()
                
                result = response.json()
                
                # Extract the summary using OpenAI-compatible format
                # (works for OpenAI, Groq, and other compatible providers)
                summary = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                
                return summary.strip() if summary else f"[Previous {len(messages)} messages]"
            
        except Exception as e:
            logger.error(f"Failed to generate summary: {str(e)}")
            # Fallback to simple truncation
            return f"[Previous {len(messages)} messages discussing various topics]"
    
    def _add_user_context(
        self, 
        messages: List[Dict[str, Any]], 
        user_context: str
    ) -> List[Dict[str, Any]]:
        """Add user context as a system message at the beginning"""
        return [
            {
                "role": "system",
                "content": f"User Context: {user_context}"
            },
            *messages
        ]
    
    def prepare_messages_for_agent(
        self, 
        messages: List[Dict[str, Any]], 
        compacted_messages: List[Dict[str, Any]],
        was_compacted: bool
    ) -> List[Dict[str, Any]]:
        """
        Prepare messages for sending to agent, adding metadata about compaction
        
        Args:
            messages: Original full messages
            compacted_messages: Compacted version of messages
            was_compacted: Whether compaction occurred
            
        Returns:
            Messages ready for agent with metadata
        """
        if not was_compacted:
            return compacted_messages
        
        # Add a note about compaction for transparency
        result = compacted_messages.copy()
        
        # Insert compaction notice after user context and summary
        system_messages_count = sum(1 for msg in result if msg['role'] == 'system')
        insert_position = system_messages_count
        
        result.insert(insert_position, {
            "role": "system",
            "content": f"Note: This conversation has been compacted. Showing summary of {len(messages) - len(compacted_messages) + 2} older messages and the {len(compacted_messages) - system_messages_count} most recent messages."
        })
        
        return result


# Create singleton instance
conversation_compactor = ConversationCompactor()