"""
Memory Search Service for MCP Tool

This service provides active memory search capabilities for agents,
allowing them to search their own memory during execution.
"""

import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from app.services.agent_memory_service import agent_memory_service
from app.models.agent_memory import MemorySearchRequest


async def handler(**params) -> Dict[str, Any]:
    """
    Search agent's memory with advanced filtering
    
    Parameters:
    - agent_id: str (required) - The agent's ID
    - query: str (required) - Search query
    - k: int (optional, default=5) - Number of results to return
    - filter_type: str (optional) - Filter by content type (user_message, agent_response, preference)
    - time_range: str (optional) - Time filter (last_hour, today, last_week, all)
    - min_score: float (optional, default=0.5) - Minimum similarity score
    
    Returns:
    - memories: List of matching memories with content, timestamp, score, type
    - total_found: Total number of memories found
    - search_time: Time taken to search in milliseconds
    """
    
    # Extract parameters
    agent_id = params.get('agent_id')
    query = params.get('query')
    k = params.get('k', 5)
    filter_type = params.get('filter_type')
    time_range = params.get('time_range', 'all')
    min_score = params.get('min_score', 0.5)
    
    # Validate required parameters
    if not agent_id:
        return {
            "error": "agent_id is required",
            "success": False
        }
    
    if not query:
        return {
            "error": "query is required",
            "success": False
        }
    
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
                "importance": memory.importance,
                "metadata": memory.metadata,
                "conversation_id": memory.conversation_id
            })
        
        # Calculate search time
        search_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        return {
            "success": True,
            "memories": memories,
            "total_found": len(memories),
            "search_time": round(search_time, 2),
            "query": query,
            "filters": {
                "type": filter_type,
                "time_range": time_range,
                "min_score": min_score
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Search failed: {str(e)}",
            "memories": [],
            "total_found": 0
        }