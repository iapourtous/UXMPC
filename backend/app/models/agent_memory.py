from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from bson import ObjectId
from app.models.service import PyObjectId


class AgentMemoryBase(BaseModel):
    """Base model for agent memory entries"""
    agent_id: str = Field(..., description="ID of the agent this memory belongs to")
    user_id: Optional[str] = Field(None, description="Optional user ID for user-specific memories")
    conversation_id: str = Field(..., description="Conversation/session ID")
    content: str = Field(..., description="The actual content to remember")
    content_type: str = Field(
        ..., 
        description="Type of content: user_message, agent_response, tool_call, preference, observation"
    )
    embedding: Optional[List[float]] = Field(
        None, 
        description="Vector embedding of the content for similarity search"
    )
    metadata: Dict[str, Any] = Field(
        default={}, 
        description="Additional metadata (context, importance, tags, etc.)"
    )
    importance: float = Field(
        default=0.5, 
        description="Importance score (0-1) for memory prioritization"
    )
    access_count: int = Field(
        default=0, 
        description="Number of times this memory has been accessed"
    )
    last_accessed: Optional[datetime] = Field(
        None, 
        description="Last time this memory was accessed"
    )


class AgentMemoryCreate(AgentMemoryBase):
    """Model for creating a new memory entry"""
    pass


class AgentMemoryUpdate(BaseModel):
    """Model for updating a memory entry"""
    content: Optional[str] = None
    content_type: Optional[str] = None
    embedding: Optional[List[float]] = None
    metadata: Optional[Dict[str, Any]] = None
    importance: Optional[float] = None
    access_count: Optional[int] = None
    last_accessed: Optional[datetime] = None


class AgentMemoryInDB(AgentMemoryBase):
    """Model for memory stored in database"""
    id: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str}
    }


class AgentMemory(AgentMemoryInDB):
    """Complete agent memory model"""
    pass


class MemorySearchRequest(BaseModel):
    """Request model for searching memories"""
    query: str = Field(..., description="Search query")
    k: int = Field(default=5, description="Number of results to return")
    content_types: Optional[List[str]] = Field(
        None, 
        description="Filter by content types"
    )
    user_id: Optional[str] = Field(None, description="Filter by user ID")
    min_importance: Optional[float] = Field(
        None, 
        description="Minimum importance score"
    )
    date_from: Optional[datetime] = Field(None, description="Filter memories from date")
    date_to: Optional[datetime] = Field(None, description="Filter memories to date")


class MemorySearchResult(BaseModel):
    """Result model for memory search"""
    memory: AgentMemory
    score: float = Field(..., description="Similarity score (0-1)")
    relevance_explanation: Optional[str] = Field(
        None, 
        description="Explanation of why this memory is relevant"
    )


class AgentMemorySummary(BaseModel):
    """Summary statistics for an agent's memory"""
    total_memories: int
    memories_by_type: Dict[str, int]
    recent_topics: List[str]
    frequent_topics: List[str]
    user_preferences: Dict[str, Any]
    oldest_memory: Optional[datetime]
    newest_memory: Optional[datetime]
    average_importance: float