"""
Agent Memory Service

This module provides high-level memory management for agents,
including conversation storage, context retrieval, and preference extraction.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid
import json
import logging
from app.models.agent_memory import (
    AgentMemory, AgentMemoryCreate, AgentMemoryUpdate,
    MemorySearchRequest, MemorySearchResult, AgentMemorySummary
)
from app.core.vector_store_simple import get_vector_store
from app.core.database import get_database
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

logger = logging.getLogger(__name__)


class AgentMemoryService:
    """Service for managing agent memories"""
    
    def __init__(self):
        self.vector_store = get_vector_store()
        self.collection_name = "agent_memories"
    
    async def save_conversation(
        self, 
        agent_id: str,
        conversation_id: str,
        messages: List[Dict[str, str]],
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[AgentMemory]:
        """
        Save a conversation to memory
        
        Args:
            agent_id: The agent's ID
            conversation_id: Unique conversation ID
            messages: List of messages with 'role' and 'content'
            user_id: Optional user ID
            metadata: Additional metadata for the conversation
            
        Returns:
            List of created memory entries
        """
        db = get_database()
        memories = []
        
        for i, message in enumerate(messages):
            # Determine content type based on role
            content_type = "user_message" if message['role'] == 'user' else 'agent_response'
            
            # Create memory entry
            memory_data = AgentMemoryCreate(
                agent_id=agent_id,
                user_id=user_id,
                conversation_id=conversation_id,
                content=message['content'],
                content_type=content_type,
                metadata={
                    **(metadata or {}),
                    "message_index": i,
                    "role": message['role'],
                    "timestamp": datetime.utcnow().isoformat()
                },
                importance=0.7 if content_type == 'user_message' else 0.5
            )
            
            # Save to MongoDB
            memory_dict = memory_data.dict()
            memory_dict['created_at'] = datetime.utcnow()
            memory_dict['updated_at'] = datetime.utcnow()
            
            result = await db[self.collection_name].insert_one(memory_dict)
            memory_dict['id'] = str(result.inserted_id)
            
            # Save to vector store
            self.vector_store.add_memory(
                agent_id=agent_id,
                memory_id=memory_dict['id'],
                content=message['content'],
                metadata=memory_dict['metadata']
            )
            
            memories.append(AgentMemory(**memory_dict))
        
        logger.info(f"Saved {len(memories)} conversation messages for agent {agent_id}")
        return memories
    
    async def load_context(
        self,
        agent_id: str,
        query: str,
        k: int = 5,
        user_id: Optional[str] = None,
        content_types: Optional[List[str]] = None
    ) -> List[MemorySearchResult]:
        """
        Load relevant context for a query
        
        Args:
            agent_id: The agent's ID
            query: The context query
            k: Number of memories to retrieve
            user_id: Optional filter by user
            content_types: Optional filter by content types
            
        Returns:
            List of relevant memories with scores
        """
        # Build filter
        filter_dict = {}
        if user_id:
            filter_dict['user_id'] = user_id
        if content_types:
            filter_dict['content_type'] = {"$in": content_types}
        
        # Search in vector store
        vector_results = self.vector_store.search_memories(
            agent_id=agent_id,
            query=query,
            k=k,
            filter_dict=filter_dict if filter_dict else None
        )
        
        # Load full memory objects from MongoDB
        db = get_database()
        results = []
        
        for memory_id, content, metadata, score in vector_results:
            # Get full memory from MongoDB
            memory_doc = await db[self.collection_name].find_one(
                {"_id": ObjectId(memory_id)}
            )
            
            if memory_doc:
                memory_doc['id'] = str(memory_doc['_id'])
                memory = AgentMemory(**memory_doc)
                
                # Update access count and last accessed
                await db[self.collection_name].update_one(
                    {"_id": ObjectId(memory_id)},
                    {
                        "$inc": {"access_count": 1},
                        "$set": {"last_accessed": datetime.utcnow()}
                    }
                )
                
                results.append(MemorySearchResult(
                    memory=memory,
                    score=score,
                    relevance_explanation=f"Semantic similarity: {score:.2f}"
                ))
        
        return results
    
    async def extract_preferences(
        self,
        agent_id: str,
        conversation: List[Dict[str, str]],
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Extract user preferences from a conversation
        
        Args:
            agent_id: The agent's ID
            conversation: The conversation messages
            user_id: Optional user ID
            
        Returns:
            Dictionary of extracted preferences
        """
        preferences = {}
        
        # Keywords that might indicate preferences
        preference_keywords = [
            "prefer", "like", "favorite", "always", "never", "usually",
            "love", "hate", "want", "don't want", "wish", "hope"
        ]
        
        for message in conversation:
            if message['role'] == 'user':
                content_lower = message['content'].lower()
                
                # Check for preference keywords
                for keyword in preference_keywords:
                    if keyword in content_lower:
                        # Store the preference statement
                        if 'statements' not in preferences:
                            preferences['statements'] = []
                        preferences['statements'].append({
                            "content": message['content'],
                            "keyword": keyword,
                            "timestamp": datetime.utcnow().isoformat()
                        })
                        
                        # Also save as a special memory
                        await self.save_preference(
                            agent_id=agent_id,
                            user_id=user_id,
                            preference_content=message['content'],
                            context={"keyword": keyword}
                        )
        
        return preferences
    
    async def save_preference(
        self,
        agent_id: str,
        preference_content: str,
        user_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> AgentMemory:
        """
        Save a user preference as a special memory
        
        Args:
            agent_id: The agent's ID
            preference_content: The preference statement
            user_id: Optional user ID
            context: Additional context
            
        Returns:
            Created memory entry
        """
        db = get_database()
        
        memory_data = AgentMemoryCreate(
            agent_id=agent_id,
            user_id=user_id,
            conversation_id=f"pref_{uuid.uuid4()}",
            content=preference_content,
            content_type="preference",
            metadata={
                **(context or {}),
                "timestamp": datetime.utcnow().isoformat()
            },
            importance=0.9  # High importance for preferences
        )
        
        # Save to MongoDB
        memory_dict = memory_data.dict()
        memory_dict['created_at'] = datetime.utcnow()
        memory_dict['updated_at'] = datetime.utcnow()
        
        result = await db[self.collection_name].insert_one(memory_dict)
        memory_dict['id'] = str(result.inserted_id)
        
        # Save to vector store
        self.vector_store.add_memory(
            agent_id=agent_id,
            memory_id=memory_dict['id'],
            content=preference_content,
            metadata=memory_dict['metadata']
        )
        
        return AgentMemory(**memory_dict)
    
    async def get_memory_summary(self, agent_id: str) -> AgentMemorySummary:
        """
        Get a summary of an agent's memory
        
        Args:
            agent_id: The agent's ID
            
        Returns:
            Summary statistics
        """
        db = get_database()
        
        # Get all memories for the agent
        memories = await db[self.collection_name].find(
            {"agent_id": agent_id}
        ).to_list(None)
        
        if not memories:
            return AgentMemorySummary(
                total_memories=0,
                memories_by_type={},
                recent_topics=[],
                frequent_topics=[],
                user_preferences={},
                oldest_memory=None,
                newest_memory=None,
                average_importance=0.0
            )
        
        # Calculate statistics
        memories_by_type = {}
        total_importance = 0.0
        oldest = newest = memories[0]['created_at']
        
        for memory in memories:
            # Count by type
            ct = memory.get('content_type', 'unknown')
            memories_by_type[ct] = memories_by_type.get(ct, 0) + 1
            
            # Track importance
            total_importance += memory.get('importance', 0.5)
            
            # Track dates
            created = memory['created_at']
            if created < oldest:
                oldest = created
            if created > newest:
                newest = created
        
        # Extract topics (simplified - in production, use NLP)
        recent_memories = sorted(memories, key=lambda x: x['created_at'], reverse=True)[:20]
        recent_topics = self._extract_topics([m['content'] for m in recent_memories])
        
        # Get preferences
        preference_memories = [m for m in memories if m.get('content_type') == 'preference']
        user_preferences = {
            "count": len(preference_memories),
            "samples": [m['content'] for m in preference_memories[:5]]
        }
        
        return AgentMemorySummary(
            total_memories=len(memories),
            memories_by_type=memories_by_type,
            recent_topics=recent_topics[:10],
            frequent_topics=recent_topics[:5],  # Simplified
            user_preferences=user_preferences,
            oldest_memory=oldest,
            newest_memory=newest,
            average_importance=total_importance / len(memories)
        )
    
    async def search_memories(
        self,
        agent_id: str,
        search_request: MemorySearchRequest
    ) -> List[MemorySearchResult]:
        """
        Search memories with advanced filtering
        
        Args:
            agent_id: The agent's ID
            search_request: Search parameters
            
        Returns:
            List of matching memories
        """
        # Use vector search with the query
        results = await self.load_context(
            agent_id=agent_id,
            query=search_request.query,
            k=search_request.k,
            user_id=search_request.user_id,
            content_types=search_request.content_types
        )
        
        # Apply additional filters
        filtered_results = []
        for result in results:
            # Filter by importance
            if search_request.min_importance is not None:
                if result.memory.importance < search_request.min_importance:
                    continue
            
            # Filter by date range
            if search_request.date_from is not None:
                if result.memory.created_at < search_request.date_from:
                    continue
            
            if search_request.date_to is not None:
                if result.memory.created_at > search_request.date_to:
                    continue
            
            filtered_results.append(result)
        
        return filtered_results
    
    async def clear_memories(
        self,
        agent_id: str,
        user_id: Optional[str] = None
    ) -> int:
        """
        Clear memories for an agent
        
        Args:
            agent_id: The agent's ID
            user_id: Optional - only clear memories for specific user
            
        Returns:
            Number of memories deleted
        """
        db = get_database()
        
        # Build filter
        filter_dict = {"agent_id": agent_id}
        if user_id:
            filter_dict["user_id"] = user_id
        
        # Count before deletion
        count = await db[self.collection_name].count_documents(filter_dict)
        
        # Delete from MongoDB
        await db[self.collection_name].delete_many(filter_dict)
        
        # Clear from vector store (if clearing all memories)
        if not user_id:
            self.vector_store.clear_memories(agent_id)
        else:
            # For user-specific deletion, we'd need to delete individual memories
            # This is a limitation of the current vector store design
            logger.warning("User-specific memory deletion from vector store not implemented")
        
        logger.info(f"Cleared {count} memories for agent {agent_id}")
        return count
    
    def _extract_topics(self, texts: List[str]) -> List[str]:
        """
        Extract topics from texts (simplified version)
        
        Args:
            texts: List of text contents
            
        Returns:
            List of extracted topics
        """
        # In production, use NLP techniques like TF-IDF or topic modeling
        # For now, just extract frequent words
        word_freq = {}
        stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "is", "are", "was", "were"}
        
        for text in texts:
            words = text.lower().split()
            for word in words:
                if len(word) > 3 and word not in stop_words:
                    word_freq[word] = word_freq.get(word, 0) + 1
        
        # Sort by frequency
        topics = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        return [topic[0] for topic in topics]


# Singleton instance
agent_memory_service = AgentMemoryService()