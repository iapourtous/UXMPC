"""
Demo Models

Models for storing interactive HTML/CSS/JS demos from meta-chat
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime
from bson import ObjectId
import re


class PyObjectId(ObjectId):
    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid objectid")
        return ObjectId(v)

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: type, handler
    ):
        from pydantic_core import core_schema
        return core_schema.no_info_after_validator_function(
            cls.validate,
            core_schema.str_schema(),
            serialization=core_schema.plain_serializer_function_ser_schema(
                str,
                when_used='json'
            )
        )


class DemoBase(BaseModel):
    """Base demo model"""
    name: str = Field(..., description="URL-friendly name for the endpoint (e.g., 'snake-game')")
    query: str = Field(..., description="The original user query")
    instructions: Optional[str] = Field(None, description="Custom presentation instructions if provided")
    description: str = Field(..., description="Brief description of the demo")
    html_content: str = Field(..., description="Complete HTML/CSS/JS content")
    session_id: str = Field(..., description="Meta-chat session ID for reference")
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Ensure name is URL-friendly"""
        if not re.match(r'^[a-z0-9-]+$', v):
            raise ValueError("Name must contain only lowercase letters, numbers, and hyphens")
        if len(v) < 3 or len(v) > 50:
            raise ValueError("Name must be between 3 and 50 characters")
        return v


class DemoCreate(DemoBase):
    """Model for creating a demo"""
    pass


class DemoUpdate(BaseModel):
    """Model for updating a demo"""
    description: Optional[str] = None


class DemoInDB(DemoBase):
    """Demo model as stored in database"""
    id: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    endpoint: str = Field(default="", description="Full endpoint URL")
    
    model_config = {
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str}
    }


class Demo(DemoInDB):
    """Complete demo model"""
    @property
    def full_url(self) -> str:
        """Get the full URL for accessing this demo"""
        return f"/demos/{self.name}"


class DemoList(BaseModel):
    """List of demos with pagination info"""
    demos: list[Demo]
    total: int
    page: int = 1
    per_page: int = 20