"""
Agent Memory Tools for MCP

This module provides memory management tools that are automatically
injected into agents when memory is enabled.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from app.services.agent_memory_service import agent_memory_service
from app.models.agent_memory import MemorySearchRequest, AgentMemoryCreate
import uuid
import logging

logger = logging.getLogger(__name__)


async def memory_search(
    agent_id: str,
    query: str,
    k: int = 5,
    filter_type: Optional[str] = None,
    time_range: str = 'all',
    min_score: float = 0.5
) -> Dict[str, Any]:
    """
    Search through agent's memory using semantic similarity
    
    Args:
        agent_id: The agent's ID (injected automatically)
        query: Search query to find relevant memories
        k: Number of results to return (default: 5)
        filter_type: Filter by type: user_message, agent_response, preference
        time_range: Time filter: last_hour, today, last_week, all (default: all)
        min_score: Minimum similarity score (default: 0.5)
    
    Returns:
        Dict containing search results with memories, total_found, and search_time
    """
    try:
        start_time = datetime.utcnow()
        
        # Build search request
        search_request = MemorySearchRequest(
            query=query,
            k=k,
            content_types=[filter_type] if filter_type else None,
            min_importance=min_score
        )
        
        # Add time range filter
        if time_range != 'all':
            now = datetime.utcnow()
            if time_range == 'last_hour':
                search_request.date_from = now - timedelta(hours=1)
            elif time_range == 'today':
                search_request.date_from = now.replace(hour=0, minute=0, second=0, microsecond=0)
            elif time_range == 'last_week':
                search_request.date_from = now - timedelta(days=7)
        
        # Search memories
        results = await agent_memory_service.search_memories(
            agent_id=agent_id,
            search_request=search_request
        )
        
        # Filter by minimum score
        filtered_results = [r for r in results if r.score >= min_score]
        
        # Format results
        memories = []
        for result in filtered_results:
            memory = result.memory
            memories.append({
                "id": memory.id,
                "content": memory.content,
                "type": memory.content_type,
                "timestamp": memory.created_at.isoformat(),
                "score": round(result.score, 3),
                "importance": memory.importance
            })
        
        # Calculate search time
        search_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        return {
            "success": True,
            "memories": memories,
            "total_found": len(memories),
            "search_time": round(search_time, 2),
            "query": query
        }
        
    except Exception as e:
        logger.error(f"Memory search failed: {str(e)}")
        return {
            "success": False,
            "error": f"Search failed: {str(e)}",
            "memories": [],
            "total_found": 0
        }


async def memory_store(
    agent_id: str,
    content: str,
    importance: float = 0.8,
    tags: List[str] = None,
    ttl: Optional[int] = None,
    conversation_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Store important information in agent's memory
    
    Args:
        agent_id: The agent's ID (injected automatically)
        content: Content to memorize
        importance: Importance level 0-1 (default: 0.8)
        tags: List of tags for categorization
        ttl: Time to live in hours (for working memory)
        conversation_id: Optional conversation ID
    
    Returns:
        Dict with memory_id and confirmation
    """
    try:
        # Create memory entry
        memory_data = AgentMemoryCreate(
            agent_id=agent_id,
            user_id=None,
            conversation_id=conversation_id or f"explicit_{uuid.uuid4()}",
            content=content,
            content_type="stored_knowledge",
            metadata={
                "tags": tags or [],
                "source": "explicit_store",
                "ttl_hours": ttl,
                "stored_at": datetime.utcnow().isoformat()
            },
            importance=importance
        )
        
        # Save to database
        from app.core.database import get_database
        db = get_database()
        
        memory_dict = memory_data.dict()
        memory_dict['created_at'] = datetime.utcnow()
        memory_dict['updated_at'] = datetime.utcnow()
        
        # If TTL is specified, add expiration
        if ttl:
            memory_dict['expires_at'] = datetime.utcnow() + timedelta(hours=ttl)
        
        result = await db["agent_memories"].insert_one(memory_dict)
        memory_id = str(result.inserted_id)
        
        # Save to vector store
        from app.core.memory_config import get_vector_store
        vector_store = get_vector_store()
        vector_store.add_memory(
            agent_id=agent_id,
            memory_id=memory_id,
            content=content,
            metadata=memory_dict['metadata']
        )
        
        logger.info(f"Stored memory {memory_id} for agent {agent_id}")
        
        return {
            "success": True,
            "memory_id": memory_id,
            "stored": True,
            "importance": importance,
            "ttl_hours": ttl,
            "message": "Memory stored successfully"
        }
        
    except Exception as e:
        logger.error(f"Memory store failed: {str(e)}")
        return {
            "success": False,
            "error": f"Store failed: {str(e)}",
            "stored": False
        }


async def memory_analyze(
    agent_id: str,
    analysis_type: str = "summary",
    time_range: str = "all"
) -> Dict[str, Any]:
    """
    Analyze patterns and insights from agent's memory
    
    Args:
        agent_id: The agent's ID (injected automatically)
        analysis_type: Type of analysis: summary, preferences, topics, frequency, gaps
        time_range: Time range for analysis: all, today, last_week
    
    Returns:
        Dict with analysis results, insights, and suggestions
    """
    try:
        # Get memory summary
        summary = await agent_memory_service.get_memory_summary(agent_id)
        
        # Build analysis based on type
        analysis = {
            "success": True,
            "analysis_type": analysis_type,
            "time_range": time_range,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if analysis_type == "summary":
            analysis.update({
                "total_memories": summary.total_memories,
                "memory_types": summary.memories_by_type,
                "average_importance": summary.average_importance,
                "recent_topics": summary.recent_topics[:10],
                "memory_span": {
                    "oldest": summary.oldest_memory,
                    "newest": summary.newest_memory
                }
            })
            
        elif analysis_type == "preferences":
            analysis.update({
                "user_preferences": summary.user_preferences,
                "preference_count": summary.user_preferences.get("count", 0),
                "samples": summary.user_preferences.get("samples", [])
            })
            
        elif analysis_type == "topics":
            analysis.update({
                "frequent_topics": summary.frequent_topics,
                "recent_topics": summary.recent_topics,
                "topic_distribution": {
                    topic: summary.recent_topics.count(topic) 
                    for topic in set(summary.recent_topics)
                }
            })
            
        elif analysis_type == "frequency":
            # Analyze memory creation frequency
            from app.core.database import get_database
            db = get_database()
            
            # Get memories with time filter
            filter_dict = {"agent_id": agent_id}
            if time_range != "all":
                now = datetime.utcnow()
                if time_range == "today":
                    filter_dict["created_at"] = {"$gte": now.replace(hour=0, minute=0)}
                elif time_range == "last_week":
                    filter_dict["created_at"] = {"$gte": now - timedelta(days=7)}
            
            memories = await db["agent_memories"].find(filter_dict).to_list(None)
            
            # Calculate frequency by hour/day
            frequency_by_hour = {}
            for memory in memories:
                hour = memory["created_at"].hour
                frequency_by_hour[hour] = frequency_by_hour.get(hour, 0) + 1
            
            analysis.update({
                "total_in_period": len(memories),
                "frequency_by_hour": frequency_by_hour,
                "peak_hours": sorted(frequency_by_hour.items(), key=lambda x: x[1], reverse=True)[:3]
            })
            
        elif analysis_type == "gaps":
            # Identify knowledge gaps
            analysis.update({
                "insights": [
                    f"You have {summary.total_memories} total memories",
                    f"Most memories are of type: {max(summary.memories_by_type.items(), key=lambda x: x[1])[0] if summary.memories_by_type else 'none'}",
                    f"Consider exploring topics beyond: {', '.join(summary.frequent_topics[:3])}"
                ],
                "suggestions": [
                    "Search for user preferences regularly",
                    "Store important findings with high importance",
                    "Tag memories for better organization"
                ]
            })
        
        return analysis
        
    except Exception as e:
        logger.error(f"Memory analysis failed: {str(e)}")
        return {
            "success": False,
            "error": f"Analysis failed: {str(e)}",
            "analysis_type": analysis_type
        }


# Tool definitions for MCP registration
MEMORY_TOOLS = [
    {
        "name": "memory_search",
        "description": "Search through your memory using semantic similarity. Always use this before external tools to check if you already know the answer.",
        "handler": memory_search,
        "parameters": {
            "query": {
                "type": "string",
                "description": "Search query to find relevant memories",
                "required": True
            },
            "k": {
                "type": "integer", 
                "description": "Number of results to return",
                "default": 5
            },
            "filter_type": {
                "type": "string",
                "description": "Filter by type: user_message, agent_response, preference, stored_knowledge",
                "enum": ["user_message", "agent_response", "preference", "stored_knowledge"]
            },
            "time_range": {
                "type": "string",
                "description": "Time filter for memories",
                "enum": ["last_hour", "today", "last_week", "all"],
                "default": "all"
            },
            "min_score": {
                "type": "number",
                "description": "Minimum similarity score (0-1)",
                "default": 0.5
            }
        }
    },
    {
        "name": "memory_store",
        "description": "Store important information, findings, or user preferences in your memory for future use.",
        "handler": memory_store,
        "parameters": {
            "content": {
                "type": "string",
                "description": "Content to memorize",
                "required": True
            },
            "importance": {
                "type": "number",
                "description": "Importance level (0-1)",
                "default": 0.8
            },
            "tags": {
                "type": "array",
                "description": "Tags for categorization",
                "items": {"type": "string"}
            },
            "ttl": {
                "type": "integer",
                "description": "Time to live in hours (for temporary memory)"
            }
        }
    },
    {
        "name": "memory_analyze", 
        "description": "Analyze your memory patterns to gain insights about past interactions and knowledge gaps.",
        "handler": memory_analyze,
        "parameters": {
            "analysis_type": {
                "type": "string",
                "description": "Type of analysis to perform",
                "enum": ["summary", "preferences", "topics", "frequency", "gaps"],
                "default": "summary"
            },
            "time_range": {
                "type": "string",
                "description": "Time range for analysis",
                "enum": ["all", "today", "last_week"],
                "default": "all"
            }
        }
    }
]