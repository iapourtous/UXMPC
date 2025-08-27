"""
Conversation Manager
Handles conversation creation, retrieval, and message management for agent executions
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
import json

from app.models.conversation import ConversationCreate, MessageCreate, Conversation
from app.services.conversation_crud import conversation_crud
from app.services.unified_logger import UnifiedLogger


class ConversationManager:
    """Manages conversation persistence and retrieval for agent executions"""
    
    def __init__(self, logger: Optional[UnifiedLogger] = None):
        """Initialize the conversation manager
        
        Args:
            logger: Optional logger instance for debugging
        """
        self.logger = logger
    
    async def get_or_create_conversation(
        self,
        execution_id: str,
        conversation_id: Optional[str] = None,
        create_new: bool = False
    ) -> Optional[Conversation]:
        """Get an existing conversation or create a new one
        
        Args:
            execution_id: Current execution ID
            conversation_id: Optional conversation ID to retrieve
            create_new: Force creation of a new conversation
            
        Returns:
            Conversation object or None if not saving conversation
        """
        if create_new or not conversation_id:
            # Get latest conversation or create new one
            conversation = await conversation_crud.get_latest_conversation()
            if not conversation or create_new:
                # Create new conversation
                conversation = await conversation_crud.create(
                    ConversationCreate(
                        user_id=None,  # TODO: Add user support
                        title=f"New Conversation - {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
                        metadata={"execution_id": execution_id}
                    )
                )
                if self.logger:
                    await self.logger.debug(f"Created new conversation: {conversation.id}")
            else:
                if self.logger:
                    await self.logger.debug(f"Using existing conversation: {conversation.id}")
        else:
            # Try to get existing conversation
            conversation = await conversation_crud.get(conversation_id)
            if not conversation:
                if self.logger:
                    await self.logger.warning(f"Conversation {conversation_id} not found, creating new one")
                # Create new conversation
                conversation = await conversation_crud.create(
                    ConversationCreate(
                        user_id=None,
                        title=f"New Conversation - {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
                        metadata={"execution_id": execution_id}
                    )
                )
        
        return conversation
    
    async def save_user_message(
        self,
        conversation_id: str,
        content: Any,
        execution_id: str
    ) -> None:
        """Save a user message to the conversation
        
        Args:
            conversation_id: Conversation to save to
            content: Message content (string or dict)
            execution_id: Current execution ID
        """
        user_content = content if isinstance(content, str) else json.dumps(content)
        await conversation_crud.add_message(
            conversation_id,
            MessageCreate(
                role="user",
                content=user_content,
                metadata={"execution_id": execution_id},
                agent_id=None  # User messages don't have agent_id
            )
        )
        if self.logger:
            await self.logger.debug(f"Saved user message to conversation {conversation_id}")
    
    async def save_assistant_message(
        self,
        conversation_id: str,
        content: Any,
        agent_id: str,
        execution_id: str
    ) -> None:
        """Save an assistant message to the conversation
        
        Args:
            conversation_id: Conversation to save to
            content: Message content (string or dict)
            agent_id: Agent that generated the message
            execution_id: Current execution ID
        """
        assistant_content = content if isinstance(content, str) else json.dumps(content)
        await conversation_crud.add_message(
            conversation_id,
            MessageCreate(
                role="assistant",
                content=assistant_content,
                metadata={"execution_id": execution_id},
                agent_id=agent_id
            )
        )
        if self.logger:
            await self.logger.debug(f"Saved assistant message to conversation {conversation_id}")
    
    async def load_conversation_history(
        self,
        conversation_id: str
    ) -> List[Dict[str, str]]:
        """Load conversation history in LLM-compatible format
        
        Args:
            conversation_id: Conversation to load from
            
        Returns:
            List of message dicts with 'role' and 'content' keys
        """
        conversation = await conversation_crud.get(conversation_id)
        if not conversation or not conversation.messages:
            return []
        
        history = []
        for msg in conversation.messages:
            history.append({
                "role": msg.role,
                "content": msg.content
            })
        
        if self.logger:
            await self.logger.debug(f"Loaded {len(history)} messages from conversation {conversation_id}")
        
        return history
    
    async def get_conversation_summary(
        self,
        conversation_id: str,
        max_messages: int = 10
    ) -> Dict[str, Any]:
        """Get a summary of the conversation
        
        Args:
            conversation_id: Conversation to summarize
            max_messages: Maximum number of recent messages to include
            
        Returns:
            Dictionary with conversation metadata and recent messages
        """
        conversation = await conversation_crud.get(conversation_id)
        if not conversation:
            return {
                "exists": False,
                "id": conversation_id
            }
        
        recent_messages = []
        if conversation.messages:
            # Get the last N messages
            for msg in conversation.messages[-max_messages:]:
                recent_messages.append({
                    "role": msg.role,
                    "content": msg.content[:200] if len(msg.content) > 200 else msg.content,
                    "timestamp": msg.timestamp
                })
        
        return {
            "exists": True,
            "id": conversation.id,
            "title": conversation.title,
            "created_at": conversation.created_at,
            "updated_at": conversation.updated_at,
            "message_count": len(conversation.messages) if conversation.messages else 0,
            "recent_messages": recent_messages
        }