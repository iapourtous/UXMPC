"""
Global Settings Models

Models for system-wide configuration including conversation compaction
and user context settings.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from bson import ObjectId


class ConversationCompactionSettings(BaseModel):
    """Settings for automatic conversation compaction"""
    enabled: bool = Field(True, description="Enable automatic conversation compaction")
    message_threshold: int = Field(5, ge=2, description="Compact after this many messages")
    preserve_last_n: int = Field(3, ge=1, description="Number of recent messages to preserve uncompacted")
    summary_max_tokens: int = Field(100, ge=50, le=500, description="Maximum tokens for summary of old messages")


class GlobalSettingsBase(BaseModel):
    """Base model for global settings"""
    summary_llm_profile: Optional[str] = Field(
        None, 
        description="LLM profile name to use for summarizing conversations (text-only profiles)"
    )
    user_context: Optional[str] = Field(
        None, 
        description="Persistent user context provided to all agents (e.g., user preferences, language, expertise level)"
    )
    compaction_settings: ConversationCompactionSettings = Field(
        default_factory=ConversationCompactionSettings,
        description="Configuration for automatic conversation compaction"
    )


class GlobalSettingsCreate(GlobalSettingsBase):
    """Model for creating global settings"""
    pass


class GlobalSettingsUpdate(BaseModel):
    """Model for updating global settings"""
    summary_llm_profile: Optional[str] = None
    user_context: Optional[str] = None
    compaction_settings: Optional[ConversationCompactionSettings] = None


class GlobalSettingsInDB(GlobalSettingsBase):
    """Global settings as stored in database"""
    id: Optional[str] = Field(default=None, alias="_id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda v: v.isoformat()
        }


class GlobalSettings(GlobalSettingsInDB):
    """Complete global settings model"""
    pass