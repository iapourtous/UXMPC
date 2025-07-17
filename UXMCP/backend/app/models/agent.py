from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from bson import ObjectId
from app.models.service import PyObjectId


class AgentBase(BaseModel):
    name: str = Field(..., description="Unique agent name")
    llm_profile: str = Field(..., description="Name of the LLM profile to use")
    mcp_services: List[str] = Field(default=[], description="List of MCP service names this agent can use")
    system_prompt: Optional[str] = Field(None, description="System prompt for the agent")
    pre_prompt: Optional[str] = Field(None, description="Prompt prepended to each user message")
    endpoint: str = Field(..., description="API endpoint for this agent (e.g. /api/agent/customer-support)")
    input_schema: Union[Dict[str, Any], str] = Field(
        default="text", 
        description="Input schema - either JSON schema or 'text' for plain text"
    )
    output_schema: Union[Dict[str, Any], str] = Field(
        default="text",
        description="Output schema - either JSON schema or 'text' for plain text"
    )
    description: Optional[str] = Field(None, description="Agent description")
    active: bool = Field(default=False, description="Whether the agent is active")
    
    # Advanced configuration
    temperature: Optional[float] = Field(None, description="Override LLM temperature for this agent")
    max_tokens: Optional[int] = Field(None, description="Override max tokens for this agent")
    
    # Behavior configuration
    allow_parallel_tool_calls: bool = Field(
        default=True, 
        description="Whether to allow parallel tool calls"
    )
    require_tool_use: bool = Field(
        default=False,
        description="Whether the agent must use at least one tool"
    )
    max_iterations: int = Field(
        default=5,
        description="Maximum iterations for tool use (prevents infinite loops)"
    )
    
    # 🧠 1. Backstory - Identity & Context
    backstory: Optional[str] = Field(
        None, 
        description="Agent's identity, background, and context (e.g., '15 years tax advisor', 'steampunk robot archivist')"
    )
    
    # 🎯 2. Objectives & Clear Missions
    objectives: List[str] = Field(
        default=[], 
        description="Clear objectives and missions (e.g., 'Optimize travel budget', 'Provide accurate documentation')"
    )
    
    # 🛑 3. Constraints & Limits
    constraints: List[str] = Field(
        default=[], 
        description="Limitations and restrictions (e.g., 'Never share personal data', 'Always verify facts')"
    )
    
    # 🗺️ 4. Memory & Context Persistence
    memory_enabled: bool = Field(
        default=False, 
        description="Enable persistent memory for conversation history and user preferences"
    )
    memory_config: Dict[str, Any] = Field(
        default={
            "max_memories": 1000,
            "embedding_model": "all-MiniLM-L6-v2",
            "search_k": 5
        },
        description="Memory configuration (max items, embedding model, search parameters)"
    )
    
    # 🧩 5. Mental Models & Reasoning Strategy
    reasoning_strategy: str = Field(
        default="standard",
        description="Reasoning strategy: standard, chain-of-thought, tree-of-thought, reflexion"
    )
    reasoning_config: Dict[str, Any] = Field(
        default={},
        description="Additional configuration for reasoning strategy"
    )
    
    # 🗣️ 6. Personality & Communication Style
    personality_traits: Dict[str, str] = Field(
        default={
            "tone": "professional",  # professional, friendly, casual, formal
            "verbosity": "balanced",  # concise, balanced, detailed
            "empathy": "moderate",    # low, moderate, high
            "humor": "none"          # none, subtle, moderate, frequent
        },
        description="Personality traits affecting communication style"
    )
    
    # 🧭 7. Action & Decision Policies
    decision_policies: Dict[str, Any] = Field(
        default={
            "confidence_threshold": 0.8,     # Minimum confidence to act without confirmation
            "require_confirmation": [],      # List of action types requiring confirmation
            "auto_correct_errors": True,     # Automatically retry on errors
            "explain_decisions": False,      # Explain reasoning for decisions
            "max_retries": 3                # Maximum retries for failed actions
        },
        description="Policies for making decisions and taking actions"
    )


class AgentCreate(AgentBase):
    pass


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    llm_profile: Optional[str] = None
    mcp_services: Optional[List[str]] = None
    system_prompt: Optional[str] = None
    pre_prompt: Optional[str] = None
    endpoint: Optional[str] = None
    input_schema: Optional[Union[Dict[str, Any], str]] = None
    output_schema: Optional[Union[Dict[str, Any], str]] = None
    description: Optional[str] = None
    active: Optional[bool] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    allow_parallel_tool_calls: Optional[bool] = None
    require_tool_use: Optional[bool] = None
    max_iterations: Optional[int] = None
    # New fields for 7 dimensions
    backstory: Optional[str] = None
    objectives: Optional[List[str]] = None
    constraints: Optional[List[str]] = None
    memory_enabled: Optional[bool] = None
    memory_config: Optional[Dict[str, Any]] = None
    reasoning_strategy: Optional[str] = None
    reasoning_config: Optional[Dict[str, Any]] = None
    personality_traits: Optional[Dict[str, str]] = None
    decision_policies: Optional[Dict[str, Any]] = None


class AgentInDB(AgentBase):
    id: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str}
    }


class Agent(AgentInDB):
    pass


class AgentExecution(BaseModel):
    """Model for agent execution request"""
    input: Union[Dict[str, Any], str] = Field(..., description="Input data according to agent's input schema")
    conversation_history: Optional[List[Dict[str, str]]] = Field(
        None, 
        description="Optional conversation history for context"
    )
    execution_options: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional execution options (timeout, etc.)"
    )


class AgentExecutionResponse(BaseModel):
    """Model for agent execution response"""
    success: bool
    output: Optional[Union[Dict[str, Any], str]] = Field(
        None,
        description="Output according to agent's output schema"
    )
    error: Optional[str] = None
    execution_id: Optional[str] = Field(None, description="Execution ID for log retrieval")
    tool_calls: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="List of tool calls made during execution"
    )
    iterations: Optional[int] = Field(None, description="Number of iterations used")
    usage: Optional[Dict[str, Any]] = Field(None, description="Token usage statistics")