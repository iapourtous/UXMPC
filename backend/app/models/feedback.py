"""
Feedback Models

Models for user feedback on meta-chat responses
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, Literal
from datetime import datetime
from bson import ObjectId


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


class FeedbackBase(BaseModel):
    """Base feedback model"""
    user_message: str = Field(..., description="Original user message")
    custom_instructions: Optional[str] = Field(None, description="Custom presentation instructions if provided")
    original_request: str = Field(..., description="The complete original request")
    agent_used: str = Field(..., description="Name of the agent that was used")
    agent_response: Dict[str, Any] = Field(..., description="Raw response from the agent")
    final_html_response: str = Field(..., description="Final HTML response shown to user")
    rating: Literal["positive", "negative"] = Field(..., description="User rating")
    feedback_text: Optional[str] = Field(None, description="Detailed feedback for negative ratings")
    session_id: str = Field(..., description="Session ID to link feedback to response")


class FeedbackCreate(FeedbackBase):
    """Model for creating feedback"""
    pass


class FeedbackInDB(FeedbackBase):
    """Feedback model as stored in database"""
    id: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str}
    }


class Feedback(FeedbackInDB):
    """Complete feedback model"""
    pass


class FeedbackList(BaseModel):
    """List of feedbacks with pagination info"""
    feedbacks: list[Feedback]
    total: int
    page: int
    per_page: int