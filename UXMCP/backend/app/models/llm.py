from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from bson import ObjectId
from app.models.service import PyObjectId


class LLMProfileBase(BaseModel):
    name: str
    model: str
    endpoint: Optional[str] = None
    api_key: str
    max_tokens: int = 4096
    temperature: float = 0.7
    mode: str = "json"
    system_prompt: Optional[str] = None
    description: Optional[str] = None
    active: bool = True


class LLMProfileCreate(LLMProfileBase):
    pass


class LLMProfileUpdate(BaseModel):
    name: Optional[str] = None
    model: Optional[str] = None
    endpoint: Optional[str] = None
    api_key: Optional[str] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    mode: Optional[str] = None
    system_prompt: Optional[str] = None
    description: Optional[str] = None
    active: Optional[bool] = None


class LLMProfileInDB(LLMProfileBase):
    id: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str}
    }


class LLMProfile(LLMProfileInDB):
    pass