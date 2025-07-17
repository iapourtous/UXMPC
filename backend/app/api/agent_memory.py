"""
Agent Memory API endpoints

This module provides API endpoints for managing agent memory,
including search, retrieval, and management of persistent context.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict, Any
from app.models.agent_memory import (
    AgentMemory, AgentMemoryCreate, MemorySearchRequest, 
    MemorySearchResult, AgentMemorySummary
)
from app.services.agent_memory_service import agent_memory_service
from app.services.agent_crud import agent_crud
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/{agent_id}/memory", response_model=List[AgentMemory])
async def get_agent_memories(
    agent_id: str,
    limit: int = Query(default=50, description="Maximum number of memories to return"),
    content_type: Optional[str] = Query(None, description="Filter by content type"),
    user_id: Optional[str] = Query(None, description="Filter by user ID")
):
    """
    Get recent memories for an agent
    
    Args:
        agent_id: The agent's ID
        limit: Maximum number of memories to return
        content_type: Optional filter by content type
        user_id: Optional filter by user ID
    """
    # Verify agent exists
    agent = await agent_crud.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Get memories from MongoDB with filters
    from app.core.database import get_database
    db = get_database()
    
    # Build filter
    filter_dict = {"agent_id": agent_id}
    if content_type:
        filter_dict["content_type"] = content_type
    if user_id:
        filter_dict["user_id"] = user_id
    
    # Query memories
    memories = await db["agent_memories"].find(filter_dict).sort("created_at", -1).limit(limit).to_list(limit)
    
    # Convert _id to id
    for memory in memories:
        memory['id'] = str(memory['_id'])
    
    return [AgentMemory(**memory) for memory in memories]


@router.post("/{agent_id}/memory/search", response_model=List[MemorySearchResult])
async def search_agent_memories(
    agent_id: str,
    search_request: MemorySearchRequest
):
    """
    Search agent memories using semantic similarity
    
    Args:
        agent_id: The agent's ID
        search_request: Search parameters including query and filters
    """
    # Verify agent exists
    agent = await agent_crud.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    if not agent.memory_enabled:
        raise HTTPException(
            status_code=400, 
            detail="Memory is not enabled for this agent"
        )
    
    try:
        results = await agent_memory_service.search_memories(
            agent_id=agent_id,
            search_request=search_request
        )
        return results
    except Exception as e:
        logger.error(f"Error searching memories: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{agent_id}/memory/{memory_id}")
async def delete_agent_memory(
    agent_id: str,
    memory_id: str
):
    """
    Delete a specific memory
    
    Args:
        agent_id: The agent's ID
        memory_id: The memory's ID
    """
    # Verify agent exists
    agent = await agent_crud.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    try:
        from app.core.database import get_database
        from bson import ObjectId
        db = get_database()
        
        # Delete from MongoDB
        result = await db["agent_memories"].delete_one({
            "_id": ObjectId(memory_id),
            "agent_id": agent_id
        })
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Memory not found")
        
        # Also delete from vector store
        from app.core.vector_store_simple import get_vector_store
        vector_store = get_vector_store()
        vector_store.delete_memory(agent_id, memory_id)
        
        return {
            "success": True,
            "message": "Memory deleted successfully"
        }
    except Exception as e:
        logger.error(f"Error deleting memory: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{agent_id}/memory")
async def clear_agent_memory(
    agent_id: str,
    user_id: Optional[str] = Query(None, description="Only clear memories for specific user")
):
    """
    Clear all memories for an agent
    
    Args:
        agent_id: The agent's ID
        user_id: Optional - only clear memories for specific user
    """
    # Verify agent exists
    agent = await agent_crud.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    try:
        count = await agent_memory_service.clear_memories(
            agent_id=agent_id,
            user_id=user_id
        )
        return {
            "success": True,
            "message": f"Cleared {count} memories",
            "agent_id": agent_id,
            "user_id": user_id
        }
    except Exception as e:
        logger.error(f"Error clearing memories: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{agent_id}/memory/summary", response_model=AgentMemorySummary)
async def get_agent_memory_summary(agent_id: str):
    """
    Get a summary of an agent's memory
    
    Args:
        agent_id: The agent's ID
    """
    # Verify agent exists
    agent = await agent_crud.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    try:
        summary = await agent_memory_service.get_memory_summary(agent_id)
        return summary
    except Exception as e:
        logger.error(f"Error getting memory summary: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{agent_id}/memory/save-conversation")
async def save_conversation(
    agent_id: str,
    conversation: List[Dict[str, str]],
    conversation_id: Optional[str] = None,
    user_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
):
    """
    Save a conversation to agent memory
    
    Args:
        agent_id: The agent's ID
        conversation: List of messages with 'role' and 'content'
        conversation_id: Optional conversation ID (generated if not provided)
        user_id: Optional user ID
        metadata: Optional additional metadata
    """
    # Verify agent exists
    agent = await agent_crud.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    if not agent.memory_enabled:
        raise HTTPException(
            status_code=400, 
            detail="Memory is not enabled for this agent"
        )
    
    # Generate conversation ID if not provided
    if not conversation_id:
        import uuid
        conversation_id = str(uuid.uuid4())
    
    try:
        memories = await agent_memory_service.save_conversation(
            agent_id=agent_id,
            conversation_id=conversation_id,
            messages=conversation,
            user_id=user_id,
            metadata=metadata
        )
        
        # Also extract preferences
        preferences = await agent_memory_service.extract_preferences(
            agent_id=agent_id,
            conversation=conversation,
            user_id=user_id
        )
        
        return {
            "success": True,
            "conversation_id": conversation_id,
            "memories_saved": len(memories),
            "preferences_found": len(preferences.get('statements', []))
        }
    except Exception as e:
        logger.error(f"Error saving conversation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{agent_id}/memory/stats")
async def get_memory_stats(agent_id: str):
    """
    Get memory statistics for an agent
    
    Args:
        agent_id: The agent's ID
    """
    # Verify agent exists
    agent = await agent_crud.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    try:
        from app.core.vector_store_simple import get_vector_store
        vector_store = get_vector_store()
        
        # Get stats from vector store
        vector_stats = vector_store.get_collection_stats(agent_id)
        
        # Get summary from memory service
        summary = await agent_memory_service.get_memory_summary(agent_id)
        
        return {
            "agent_id": agent_id,
            "memory_enabled": agent.memory_enabled,
            "memory_config": agent.memory_config,
            "vector_store_stats": vector_stats,
            "memory_summary": summary
        }
    except Exception as e:
        logger.error(f"Error getting memory stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))