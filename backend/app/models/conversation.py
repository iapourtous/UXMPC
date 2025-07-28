from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from bson import ObjectId


class MessageBase(BaseModel):
    """Base message model"""
    role: str = Field(..., description="Message role (user, assistant, system)")
    content: str = Field(..., description="Message content")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Message timestamp")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional message metadata")
    tool_calls: Optional[List[Dict[str, Any]]] = Field(None, description="Tool calls made during this message")
    execution_id: Optional[str] = Field(None, description="Execution ID if message was from agent execution")
    agent_id: Optional[str] = Field(None, description="ID of the agent that generated this message (for assistant messages)")


class ConversationBase(BaseModel):
    """Base conversation model"""
    user_id: Optional[str] = Field(None, description="Optional user ID for user-specific conversations")
    title: Optional[str] = Field(None, description="Conversation title (auto-generated or user-provided)")
    messages: List[MessageBase] = Field(default_factory=list, description="List of messages in the conversation")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional conversation metadata")
    active: bool = Field(True, description="Whether the conversation is active")
    last_activity: datetime = Field(default_factory=datetime.utcnow, description="Last activity timestamp")
    agents_used: List[str] = Field(default_factory=list, description="List of agent IDs used in this conversation")


class ConversationCreate(ConversationBase):
    """Model for creating a conversation"""
    pass


class ConversationUpdate(BaseModel):
    """Model for updating a conversation"""
    title: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    active: Optional[bool] = None


class MessageCreate(BaseModel):
    """Model for adding a message to a conversation"""
    role: str = Field(..., description="Message role (user, assistant, system)")
    content: str = Field(..., description="Message content")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional message metadata")
    tool_calls: Optional[List[Dict[str, Any]]] = Field(None, description="Tool calls made during this message")
    execution_id: Optional[str] = Field(None, description="Execution ID if message was from agent execution")
    agent_id: Optional[str] = Field(None, description="ID of the agent that generated this message (for assistant messages)")


class ConversationInDB(ConversationBase):
    """Model for conversation in database"""
    id: str = Field(alias="_id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True


class Conversation(ConversationBase):
    """Model for conversation in API responses"""
    id: str = Field(alias="_id")
    created_at: datetime
    updated_at: datetime
    message_count: int = Field(0, description="Total number of messages in the conversation")

    class Config:
        populate_by_name = True

    @classmethod
    def from_db(cls, db_obj: ConversationInDB) -> "Conversation":
        """Create Conversation from database object"""
        return cls(
            **db_obj.dict(by_alias=True),
            message_count=len(db_obj.messages)
        )


class ConversationList(BaseModel):
    """Model for paginated conversation list"""
    items: List[Conversation]
    total: int
    page: int
    page_size: int
    total_pages: int


class ConversationSummary(BaseModel):
    """Lightweight conversation model for lists"""
    id: str = Field(alias="_id")
    title: Optional[str]
    message_count: int
    last_activity: datetime
    created_at: datetime
    active: bool
    agents_used: List[str] = Field(default_factory=list)

    class Config:
        populate_by_name = True