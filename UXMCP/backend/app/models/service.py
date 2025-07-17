from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from bson import ObjectId


from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema


class PyObjectId(ObjectId):
    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid objectid")
        return ObjectId(v)

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: type, handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls.validate,
            core_schema.str_schema(),
            serialization=core_schema.plain_serializer_function_ser_schema(
                str,
                when_used='json'
            )
        )


class ServiceParam(BaseModel):
    name: str
    type: str
    required: bool = True
    description: Optional[str] = None


class ServiceBase(BaseModel):
    name: str
    service_type: str = "tool"  # "tool", "resource", "prompt"
    route: str
    method: str = "GET"
    params: List[ServiceParam] = []
    code: str
    dependencies: List[str] = []
    input_schema: Optional[Dict[str, Any]] = None  # MCP input schema (override auto-generated)
    output_schema: Optional[Dict[str, Any]] = None  # MCP output schema for tools (FastMCP 2.10+)
    llm_profile: Optional[str] = None
    description: Optional[str] = None
    documentation: Optional[str] = None
    # Resource-specific fields
    mime_type: Optional[str] = None
    # Prompt-specific fields
    prompt_template: Optional[str] = None
    prompt_args: List[ServiceParam] = []
    active: bool = False


class ServiceCreate(ServiceBase):
    pass


class ServiceUpdate(BaseModel):
    name: Optional[str] = None
    service_type: Optional[str] = None
    route: Optional[str] = None
    method: Optional[str] = None
    params: Optional[List[ServiceParam]] = None
    code: Optional[str] = None
    dependencies: Optional[List[str]] = None
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None
    llm_profile: Optional[str] = None
    description: Optional[str] = None
    documentation: Optional[str] = None
    mime_type: Optional[str] = None
    prompt_template: Optional[str] = None
    prompt_args: Optional[List[ServiceParam]] = None


class ServiceInDB(ServiceBase):
    id: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str}
    }


class Service(ServiceInDB):
    pass